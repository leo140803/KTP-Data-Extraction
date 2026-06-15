"""
Integration tests yang memanggil OpenAI API secara nyata.
Jalankan dengan: pytest -m integration

Memerlukan:
- OPENAI_API_KEY di environment atau .env
- File foto KTP di tests/fixtures/sample_ktp.jpg
"""

import os
from pathlib import Path

import pytest


@pytest.mark.integration
def test_real_ktp_extraction():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY tidak tersedia")

    sample = Path(__file__).parent / "fixtures" / "sample_ktp.jpg"
    if not sample.exists():
        pytest.skip("Tidak ada file sample_ktp.jpg di tests/fixtures/")

    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    with open(sample, "rb") as f:
        response = client.post(
            "/ocr/extract",
            files={"file": ("sample_ktp.jpg", f, "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is not None

    data = body["data"]
    # NIK jika terekstrak harus 16 digit
    if data.get("nik"):
        assert len(data["nik"]) == 16
        assert data["nik"].isdigit()

    # Jenis kelamin harus salah satu dari nilai valid
    if data.get("jenis_kelamin"):
        assert data["jenis_kelamin"] in {"LAKI-LAKI", "PEREMPUAN"}

    print(f"\nHasil ekstraksi KTP:")
    for field, value in data.items():
        if value is not None:
            print(f"  {field}: {value}")
