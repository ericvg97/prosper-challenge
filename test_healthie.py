"""Integration tests for Healthie EHR functions.

These tests run against real Healthie — they require HEALTHIE_EMAIL,
HEALTHIE_PASSWORD, and OPENAI_API_KEY to be set (loaded via conftest.py).
"""

from datetime import date, time

import pytest

from healthie import find_patient, create_appointment


KNOWN_PATIENT_NAME = "Eric Smith"
KNOWN_PATIENT_DOB = date(2026, 4, 14)
KNOWN_PATIENT_ID = "14791913"



class TestFindPatient:
    async def test_finds_existing_patient(self):
        patient_id = await find_patient(KNOWN_PATIENT_NAME, KNOWN_PATIENT_DOB)
        assert patient_id == KNOWN_PATIENT_ID

    async def test_returns_none_for_unknown_patient(self):
        patient_id = await find_patient("Nonexistent Person", date(1900, 1, 1))
        assert patient_id is None

    async def test_wrong_dob_returns_none(self):
        patient_id = await find_patient(KNOWN_PATIENT_NAME, date(1990, 1, 1))
        assert patient_id is None


class TestCreateAppointment:
    async def test_creates_appointment_and_returns_id(self):
        appointment_id = await create_appointment(
            KNOWN_PATIENT_ID,
            date(2026, 5, 15),
            time(10, 0),
        )
        assert appointment_id is not None
        assert isinstance(appointment_id, str)
