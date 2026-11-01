"""Official source endpoints and access/licensing boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    title: str
    source_url: str
    api_url: str | None
    license_note: str
    access_note: str
    raw_format: str


SOURCES = {
    "medlineplus": SourceConfig(
        "medlineplus",
        "MedlinePlus Connect",
        "https://medlineplus.gov/medlineplus-connect/",
        "https://connect.medlineplus.gov/service",
        "Follow MedlinePlus item-level copyright and attribution terms; do not assume all linked content is public domain.",
        "Code lookup service; supports English and Spanish, not Arabic. Requires known ICD-10-CM, NDC, RxCUI, LOINC, or CPT codes.",
        "json",
    ),
    "disease_ontology": SourceConfig(
        "disease_ontology",
        "Human Disease Ontology",
        "https://disease-ontology.org/downloads/",
        "https://api.github.com/repos/DiseaseOntology/HumanDiseaseOntology/releases/latest",
        "See the Disease Ontology project's current license and attribution requirements.",
        "Public release assets; release selection is discovered from the official project GitHub API.",
        "obo",
    ),
    "hpo": SourceConfig(
        "hpo",
        "Human Phenotype Ontology",
        "https://hpo.jax.org/",
        "https://api.github.com/repos/obophenotype/human-phenotype-ontology/releases/latest",
        "See the HPO license and attribution requirements for each release.",
        "Public release asset; downloaded without clinical interpretation.",
        "json",
    ),
    "icd10": SourceConfig(
        "icd10",
        "WHO ICD-10",
        "https://www.who.int/standards/classifications/classification-of-diseases",
        None,
        "WHO ICD-10 distribution and reuse terms must be verified for the specific licensed file.",
        "No unauthenticated bulk API is assumed. Import the official file obtained under the user's applicable terms.",
        "source archive",
    ),
    "openfda": SourceConfig(
        "openfda",
        "openFDA Drug Labeling API",
        "https://open.fda.gov/apis/drug/label/",
        "https://api.fda.gov/drug/label.json",
        "FDA labeling is sourced from submitted product labeling; openFDA warns it may not be current or FDA-verified.",
        "Public API; send a bounded, explicit search query. API key is optional and read from OPENFDA_API_KEY.",
        "json",
    ),
    "rxnorm": SourceConfig(
        "rxnorm",
        "NLM RxNorm and RxNav",
        "https://www.nlm.nih.gov/research/umls/rxnorm/",
        "https://rxnav.nlm.nih.gov/REST",
        "RxNorm is a non-proprietary NLM vocabulary; RxNav API terms of service still apply.",
        "Public API; exact terminology search and interaction lookups require known drug names or RxCUIs.",
        "json",
    ),
    "loinc": SourceConfig(
        "loinc",
        "LOINC",
        "https://loinc.org/downloads/",
        None,
        "LOINC download is governed by its license and requires an eligible LOINC account; do not redistribute without permission.",
        "Import a locally downloaded licensed archive. The pipeline does not automate credentialed downloads.",
        "zip",
    ),
    "medquad": SourceConfig(
        "medquad",
        "MedQuAD dataset",
        "https://github.com/abachaa/MedQuAD",
        "https://api.github.com/repos/abachaa/MedQuAD",
        "GitHub reports NOASSERTION for the repository license; rights are unresolved. Do not use or redistribute without permission.",
        "Downloader is blocked unless explicitly overridden for a rights review copy. Never publish this material into the live content library.",
        "zip",
    ),
    "snomed": SourceConfig(
        "snomed",
        "SNOMED CT",
        "https://www.snomed.org/",
        None,
        "SNOMED CT is subject to licensing and country/affiliate restrictions.",
        "Optional local RF2 archive import only; obtain and use under an applicable SNOMED CT license.",
        "zip",
    ),
    "mesh": SourceConfig(
        "mesh",
        "Medical Subject Headings",
        "https://meshb.nlm.nih.gov/",
        "https://id.nlm.nih.gov/mesh/lookup",
        "See current NLM MeSH terms and attribution requirements.",
        "NLM lookup API; targeted descriptor lookup only, not a full terminology export.",
        "json",
    ),
    "pubmed": SourceConfig(
        "pubmed",
        "PubMed E-utilities",
        "https://pubmed.ncbi.nlm.nih.gov/",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "PubMed metadata is not a blanket license to redistribute article full text; respect item-level rights.",
        "A bounded explicit query is required. The pipeline stores citation metadata/abstract records only.",
        "xml",
    ),
}

