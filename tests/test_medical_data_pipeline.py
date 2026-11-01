from __future__ import annotations

import json
import argparse
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError
from scripts.medical_data.downloaders.hpo import HPODownloader
from scripts.medical_data.downloaders.loinc import LOINCDownloader
from scripts.medical_data.downloaders.medlineplus import MedlinePlusDownloader
from scripts.medical_data.downloaders.medquad import MedQuADDownloader
from scripts.medical_data.orchestrator import (
    _summarize_download,
    acquire,
    main,
    process_downloads,
)
from scripts.medical_data.processors.merge import merge_exact
from scripts.medical_data.processors.finalize import build_final_drafts
from scripts.medical_data.processors.normalize import parse_hpo, parse_obo, parse_pubmed_xml
from scripts.medical_data.processors.translate import translate_record
from scripts.medical_data.processors.validate import validate_processed_records, validate_raw_tree


class MedicalDataPipelineTests(unittest.TestCase):
    def test_raw_artifact_gets_checksum_and_source_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            downloader = BaseDownloader("disease_ontology", Path(temporary))
            artifact = downloader.save_raw(
                b"source data",
                "ontology.obo",
                request_url="https://example.org/ontology.obo?api_key=secret",
                content_type="text/plain",
                license_status="review_required",
            )

            metadata = json.loads(artifact.with_suffix(".obo.metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["sha256"], "7ceed356ee3b63957db5803d56072b0d8e51df6b0c2c004b789e37e379999890")
            self.assertEqual(
                parse_qs(urlsplit(metadata["request_url"]).query)["api_key"],
                ["[REDACTED]"],
            )
            self.assertEqual(validate_raw_tree(Path(temporary)), [])
            signed_url = BaseDownloader._safe_request_url(
                "https://files.example.org/data.json?sig=secret&expires=soon"
            )
            self.assertEqual(signed_url, "https://files.example.org/data.json")

    def test_medlineplus_rejects_unsupported_arabic_before_http(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            downloader = MedlinePlusDownloader(Path(temporary))
            with patch.object(downloader, "request_json") as request:
                with self.assertRaisesRegex(ValueError, "supports en and es"):
                    downloader.fetch_condition("E11.9", lang="ar")
            request.assert_not_called()

    def test_medlineplus_stores_source_response_and_accepts_known_code(self) -> None:
        response = {"feed": {"entry": [{"title": "Source title", "link": "https://medlineplus.gov/example"}]}}
        with tempfile.TemporaryDirectory() as temporary:
            downloader = MedlinePlusDownloader(Path(temporary))
            with patch.object(downloader, "request_json", return_value=(response, "https://connect.medlineplus.gov/service")):
                result = downloader.fetch_condition("E11.9", lang="en")
            self.assertEqual(result, response)
            self.assertTrue((Path(temporary) / "medlineplus" / "E11_9_en.json").is_file())

    def test_medlineplus_parses_atom_json_and_empty_match(self) -> None:
        parsed = MedlinePlusDownloader.parse_response(
            {
                "feed": {
                    "author": {"name": {"_value": "NLM"}},
                    "updated": {"_value": "2026-01-01"},
                    "entry": [
                        {
                            "id": {"_value": "topic-1"},
                            "title": {"_value": "Source title"},
                            "summary": {"_value": "<p>Source summary</p>"},
                            "link": [{"href": "https://medlineplus.gov/topic.html"}],
                        }
                    ]
                }
            }
        )
        self.assertEqual(parsed["title"], "Source title")
        self.assertEqual(parsed["summary"], "<p>Source summary</p>")
        self.assertEqual(parsed["url"], "https://medlineplus.gov/topic.html")
        self.assertEqual(parsed["author"], "NLM")
        self.assertIsNone(MedlinePlusDownloader.parse_response({"feed": {"entry": []}}))
        with self.assertRaisesRegex(ValueError, "no feed object"):
            MedlinePlusDownloader.parse_response({})

    def test_medlineplus_fetch_conditions_deduplicates_code_and_saves_gated_results(self) -> None:
        response = {
            "feed": {
                "entry": [
                    {
                        "title": {"_value": "Source title"},
                        "summary": {"_value": "Source summary"},
                        "link": [{"href": "https://medlineplus.gov/topic.html"}],
                    }
                ]
            }
        }
        conditions = [
            {
                "condition_id": "condition_a",
                "icd10_codes": ["E11.9"],
                "record_type": "condition_content_candidate",
            },
            {
                "condition_id": "condition_b",
                "icd10_crosswalks": [
                    {"coding_system": "ICD-10-CM", "code": "E11.9"}
                ],
            },
            {"condition_id": "condition_without_code"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            downloader = MedlinePlusDownloader(Path(temporary))
            with (
                patch.object(downloader, "fetch_condition", return_value=response) as fetch,
                patch("scripts.medical_data.downloaders.medlineplus.time.sleep"),
            ):
                results = downloader.fetch_conditions(conditions, delay_seconds=0)
            self.assertEqual(fetch.call_count, 2)
            fetch.assert_any_call("E11.9", lang="en")
            fetch.assert_any_call("E11.9", lang="es")
            self.assertEqual(results["condition_a"]["result_status"], "matched")
            self.assertEqual(
                results["condition_a"]["code_results"][0]["source_condition_ids"],
                ["condition_a", "condition_b"],
            )
            self.assertEqual(results["condition_without_code"]["result_status"], "no_icd10_cm_code")
            self.assertTrue(results["condition_a"]["not_for_clinical_use"])
            artifact = downloader.save_results(results)
            metadata = json.loads(
                artifact.with_suffix(".json.metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                metadata["license_status"],
                "item_level_terms_and_attribution_review_required",
            )

    def test_medlineplus_condition_batch_rejects_arabic_and_more_than_500_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            downloader = MedlinePlusDownloader(Path(temporary))
            with self.assertRaisesRegex(ValueError, "supports only en and es"):
                downloader.fetch_conditions([], languages=("ar",))
            records = [
                {"condition_id": f"condition_{index}", "icd10_code": f"A{index:02d}"}
                for index in range(501)
            ]
            with self.assertRaisesRegex(ValueError, "At most 500"):
                downloader.fetch_conditions(records, languages=("en",), delay_seconds=0)

    def test_hpo_download_requests_release_asset_once_and_checks_graph(self) -> None:
        release = {
            "tag_name": "v-test",
            "assets": [{"name": "hp-base.json", "browser_download_url": "https://github.com/example/hp.json"}],
        }
        body = json.dumps({"graphs": [{"nodes": []}]}).encode()
        with tempfile.TemporaryDirectory() as temporary:
            downloader = HPODownloader(Path(temporary))
            with (
                patch.object(downloader, "request_json", return_value=(release, "https://api.github.com/release")),
                patch.object(downloader, "request_bytes", return_value=(body, "application/json", "https://github.com/example/hp.json")) as request,
            ):
                result = downloader.fetch_all()
            request.assert_called_once()
            self.assertEqual(result["release"], "v-test")
            self.assertEqual(result["term_graph_count"], 1)

    def test_medquad_download_fails_closed_on_unasserted_license(self) -> None:
        repository = {
            "license": {"spdx_id": "NOASSERTION"},
            "default_branch": "main",
        }
        with tempfile.TemporaryDirectory() as temporary:
            downloader = MedQuADDownloader(Path(temporary))
            with patch.object(downloader, "request_json", return_value=(repository, "https://api.github.com/repo")):
                with self.assertRaisesRegex(PermissionError, "NOASSERTION"):
                    downloader.fetch_all()

    def test_source_download_failure_is_reported_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = argparse.Namespace(
                sources=["disease_ontology", "hpo"],
                allow_unverified_license=False,
                medlineplus_codes=[],
                language="en",
                openfda_search="",
                max_results=5,
                rxnorm_names=[],
                rxcuis=[],
                mesh_terms=[],
                pubmed_query="",
            )
            with (
                patch("scripts.medical_data.orchestrator.RAW_ROOT", root / "raw"),
                patch("scripts.medical_data.orchestrator.PROCESSED_ROOT", root / "processed"),
                patch("scripts.medical_data.orchestrator.DiseaseOntologyDownloader") as do_downloader,
                patch("scripts.medical_data.orchestrator.HPODownloader") as hpo_downloader,
                patch("scripts.medical_data.orchestrator.process_downloads", return_value={}),
                patch("scripts.medical_data.orchestrator.validate_raw_tree", return_value=[]) as validate_raw,
            ):
                do_downloader.return_value.fetch_all.side_effect = DownloadError("HTTP 404")
                hpo_downloader.return_value.fetch_all.return_value = {"release": "test"}
                report = acquire(args)
            self.assertEqual(report["status"], "partial")
            self.assertIn("HTTP 404", report["source_errors"]["disease_ontology"])
            self.assertEqual(report["sources"]["hpo"]["release"], "test")
            self.assertEqual(
                [call.args[0] for call in validate_raw.call_args_list],
                [root / "raw" / "disease_ontology", root / "raw" / "hpo"],
            )

    def test_cli_returns_nonzero_for_partial_acquisition(self) -> None:
        report = {
            "status": "partial",
            "source_errors": {"rxnorm": "interaction endpoint returned HTTP 404"},
        }
        output = StringIO()
        with patch("scripts.medical_data.orchestrator.acquire", return_value=report):
            with redirect_stdout(output):
                exit_code = main(["--sources", "hpo"])
        self.assertEqual(exit_code, 2)
        self.assertIn("interaction endpoint returned HTTP 404", output.getvalue())

    def test_process_only_cli_does_not_require_download_sources(self) -> None:
        with patch("scripts.medical_data.orchestrator.process_downloads", return_value={"hpo": 1}):
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(["--process-only"])
        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "processed"', output.getvalue())

    def test_run_summary_does_not_copy_source_payloads(self) -> None:
        args = argparse.Namespace(
            medlineplus_codes=[],
        )
        source_rows = [{"openfda": {"generic_name": ["metformin"]}, "warnings": ["source text"]}]

        summary = _summarize_download("openfda", source_rows, args)

        self.assertEqual(summary["record_count"], 1)
        self.assertNotIn("warnings", summary)
        self.assertNotIn("metformin", json.dumps(summary))

    def test_loinc_local_import_validates_zip_without_extracting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "licensed-loinc.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("Loinc.csv", "LOINC_NUM,LONG_COMMON_NAME\n1234-5,Example test\n")
            downloader = LOINCDownloader(Path(temporary) / "raw")
            artifact = downloader.fetch_all(archive_path)
            self.assertEqual(artifact.read_bytes(), archive_path.read_bytes())
            self.assertTrue(artifact.with_suffix(".zip.metadata.json").is_file())

    def test_obo_normalization_preserves_exact_source_and_unicode(self) -> None:
        records = parse_obo(
            'format-version: 1.2\n\n[Term]\nid: DOID:123\nname: example disease\ndef: "maladie café" [PMID:123]\nsynonym: "alternate" EXACT []\nxref: ICD10CM:"E11.9" ! type 2 diabetes\nis_a: DOID:10 ! parent disease\n',
            "https://raw.githubusercontent.com/DiseaseOntology/repo/tag/doid.obo",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["definition_source_text"], "maladie café")
        self.assertEqual(records[0]["synonyms_en"], ["alternate"])
        self.assertEqual(records[0]["icd10cm_codes"], ["E11.9"])
        self.assertEqual(records[0]["ontology_parents"], ["DOID:10"])
        self.assertEqual(records[0]["content_status"], "draft")

    def test_hpo_normalizes_phenotype_terms_without_calling_them_symptoms(self) -> None:
        terms = parse_hpo(
            {
                "graphs": [
                    {
                        "nodes": [
                            {
                                "id": "http://purl.obolibrary.org/obo/HP_0000001",
                                "lbl": "Phenotypic abnormality",
                                "meta": {
                                    "definition": {"val": "definition"},
                                    "deprecated": True,
                                    "xrefs": [{"val": "ICD-10:R50.9"}],
                                },
                            }
                        ]
                    }
                ]
            },
            "https://hpo.jax.org/data",
        )
        self.assertEqual(terms[0]["phenotype_id"], "HP:0000001")
        self.assertNotIn("symptom_id", terms[0])
        self.assertTrue(terms[0]["is_deprecated"])
        self.assertEqual(terms[0]["external_xrefs"], ["ICD-10:R50.9"])
        self.assertEqual(terms[0]["content_status"], "draft")

    def test_final_drafts_keep_exact_mappings_and_hpo_phenotype_semantics(self) -> None:
        conditions, phenotypes, code_index, report = build_final_drafts(
            {
                "source_release": "do-test",
                "source_sha256": "abc",
                "records": [
                    {
                        "condition_id": "doid_123",
                        "ontology_id": "DOID:123",
                        "condition_en": "Example condition",
                        "icd10cm_codes": ["E11.9"],
                        "external_xrefs": ['ICD10CM:"E11.9"'],
                        "references": [
                            {
                                "source": "Disease Ontology",
                                "title": "Test source",
                                "url": "https://example.org/doid.obo",
                            }
                        ],
                        "is_obsolete": False,
                    },
                    {
                        "condition_id": "doid_124",
                        "ontology_id": "DOID:124",
                        "condition_en": "Obsolete condition",
                        "is_obsolete": True,
                    },
                ],
            },
            {
                "source_release": "hpo-test",
                "source_sha256": "def",
                "records": [
                    {
                        "phenotype_id": "HP:0000001",
                        "name_en": "Observed phenotype",
                        "external_xrefs": ["DOID:123", "ICD-10:R50.9"],
                        "is_deprecated": False,
                        "references": [],
                    },
                    {
                        "phenotype_id": "HP:0000002",
                        "name_en": "Deprecated phenotype",
                        "is_deprecated": True,
                    },
                ],
            },
            {
                "records": [
                    {
                        "query_url": (
                            "https://connect.medlineplus.gov/service?"
                            "mainSearchCriteria.v.c=E11.9&"
                            "mainSearchCriteria.v.cs=2.16.840.1.113883.6.90"
                        ),
                        "title_source_text": {"_value": "Source title"},
                        "source_url": [{"href": "https://medlineplus.gov/example"}],
                    }
                ]
            },
        )
        self.assertEqual(len(conditions), 1)
        self.assertEqual(conditions[0]["icd10_crosswalks"][0]["code"], "E11.9")
        self.assertEqual(
            conditions[0]["icd10_crosswalks"][0]["source_urls"],
            ["https://example.org/doid.obo"],
        )
        self.assertEqual(conditions[0]["related_phenotype_ids"], ["HP:0000001"])
        self.assertEqual(conditions[0]["supporting_source_links"][0]["url"], "https://medlineplus.gov/example")
        self.assertEqual(len(phenotypes), 1)
        self.assertFalse(phenotypes[0]["clinical_symptom"])
        self.assertFalse(phenotypes[0]["symptom_catalog_eligible"])
        self.assertEqual(phenotypes[0]["related_condition_ids"], ["doid_123"])
        self.assertEqual(phenotypes[0]["icd_code_xrefs"][0]["coding_system"], "ICD-10")
        self.assertEqual(code_index[0]["code"], "E11.9")
        self.assertEqual(report["excluded"]["conditions"]["obsolete"], 1)
        self.assertEqual(report["excluded"]["phenotypes"]["deprecated"], 1)

    def test_pubmed_extracts_citation_without_abstract_text(self) -> None:
        citations = parse_pubmed_xml(
            b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Example <i>citation</i></ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>",
            "https://pubmed.ncbi.nlm.nih.gov/",
        )
        self.assertEqual(citations[0]["citation_id"], "PMID:123")
        self.assertEqual(citations[0]["title"], "Example citation")
        self.assertNotIn("abstract", citations[0])

    def test_merge_uses_exact_identifiers_and_retains_conflicts(self) -> None:
        records = merge_exact(
            [
                {"condition_id": "DOID:1", "name": "A", "sources": ["DO"]},
                {"condition_id": "DOID:1", "name": "B", "sources": ["HPO"]},
                {"condition_id": "DOID:2", "name": "A", "sources": ["other"]},
            ]
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["_source_conflicts"]["name"], ["A", "B"])
        self.assertEqual(records[0]["sources"], ["DO", "HPO"])

    def test_translation_stage_does_not_fabricate_translated_text(self) -> None:
        original = {"name_en": "Known source phrase"}
        result = translate_record(original, enabled=True)
        self.assertEqual(result["name_en"], "Known source phrase")
        self.assertEqual(result["translation_status"], "requires_human_review")
        self.assertNotIn("name_ar", result)

    def test_pipeline_outputs_draft_candidates_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw"
            processed = root / "processed"
            (raw / "disease_ontology").mkdir(parents=True)
            obo_path = raw / "disease_ontology" / "doid.obo"
            obo_path.write_text(
                "[Term]\nid: DOID:1\nname: test condition\n",
                encoding="utf-8",
            )
            metadata = {
                "final_url": "https://disease-ontology.org/downloads/",
                "source_url": "https://disease-ontology.org/downloads/",
            }
            obo_path.with_suffix(".obo.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            with (
                patch("scripts.medical_data.orchestrator.RAW_ROOT", raw),
                patch("scripts.medical_data.orchestrator.PROCESSED_ROOT", processed),
            ):
                counts = process_downloads()
            output = json.loads(
                (processed / "conditions" / "disease_ontology_candidates.json").read_text(encoding="utf-8")
            )
            self.assertEqual(counts["disease_ontology_candidates"], 1)
            self.assertTrue(output["clinical_review_required"])
            self.assertEqual(output["records"][0]["content_status"], "draft")
            self.assertEqual(validate_processed_records(output["records"]), [])


if __name__ == "__main__":
    unittest.main()
