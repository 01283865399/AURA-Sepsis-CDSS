from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend import main


class PatientDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_patch = patch.dict(
            os.environ,
            {
                "SEPSIS_PATIENT_DB": os.path.join(self.temp_directory.name, "patients.sqlite3"),
                "PATIENT_STORAGE_BACKEND": "sqlite",
            },
        )
        self.database_patch.start()
        self.supabase_patch = patch.object(main, "_supabase_client", None)
        self.supabase_patch.start()

    def tearDown(self) -> None:
        self.supabase_patch.stop()
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def test_create_list_and_get_patient(self) -> None:
        patient = main.create_patient(main.PatientCreateRequest(
            name="  Example Patient  ",
            age=47,
            bed_number="B-12",
            gender="Female",
        ))

        self.assertEqual(patient.name, "Example Patient")
        self.assertEqual(patient.vital_signs, {"Age": 47.0, "Gender": 0.0})
        self.assertEqual(patient.risk_tier, "Not assessed")
        self.assertEqual(main.list_patients(), [patient])
        self.assertEqual(main.get_patient(patient.patient_id), patient)

    def test_create_rejects_blank_name_and_bed(self) -> None:
        with self.assertRaises(HTTPException) as name_error:
            main.create_patient(main.PatientCreateRequest(
                name="   ",
                age=30,
                bed_number="A-1",
            ))
        self.assertEqual(name_error.exception.status_code, 422)

        with self.assertRaises(HTTPException) as bed_error:
            main.create_patient(main.PatientCreateRequest(
                name="Example Patient",
                age=30,
                bed_number="   ",
            ))
        self.assertEqual(bed_error.exception.status_code, 422)

    def test_get_unknown_patient_returns_not_found(self) -> None:
        with self.assertRaises(HTTPException) as error:
            main.get_patient("missing-patient")
        self.assertEqual(error.exception.status_code, 404)

    def test_patient_schema_validates_age_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            main.PatientCreateRequest(
                name="Example Patient",
                age=121,
                bed_number="A-1",
            )

    def test_supabase_storage_uses_client_and_returns_records(self) -> None:
        os.environ["PATIENT_STORAGE_BACKEND"] = "supabase"
        query = MagicMock()
        client = MagicMock()
        client.table.return_value = query
        query.select.return_value = query
        query.order.return_value = query
        query.insert.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        main._supabase_client = client

        created_at = "2026-10-01T13:00:00+00:00"
        inserted_row = {
            "patient_id": "60235a1c-df91-4384-8f2d-c23e4888fd94",
            "name": "Supabase Patient",
            "age": 35,
            "bed_number": "S-3",
            "gender": "Male",
            "risk_tier": "Not assessed",
            "vital_signs": {"Age": 35.0, "Gender": 1.0},
            "created_at": created_at,
        }

        query.execute.side_effect = [
            SimpleNamespace(data=[inserted_row]),
            SimpleNamespace(data=[inserted_row]),
            SimpleNamespace(data=[inserted_row]),
        ]

        created = main.create_patient(main.PatientCreateRequest(
            name="Supabase Patient",
            age=35,
            bed_number="S-3",
            gender="Male",
        ))
        self.assertEqual(created.patient_id, inserted_row["patient_id"])
        self.assertEqual(main.list_patients(), [created])
        self.assertEqual(main.get_patient(created.patient_id), created)
        client.table.assert_called_with("patients")

    def test_supabase_without_server_credentials_returns_service_unavailable(self) -> None:
        os.environ["PATIENT_STORAGE_BACKEND"] = "supabase"
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_SECRET_KEY", None)
        os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

        with self.assertRaises(HTTPException) as error:
            main.list_patients()

        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("SUPABASE_URL", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
