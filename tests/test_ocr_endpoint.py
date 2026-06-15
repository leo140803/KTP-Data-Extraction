from unittest.mock import patch, MagicMock

import pytest


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestExtractEndpoint:
    def test_success_returns_200_with_ktp_data(
        self, client, valid_jpeg_bytes, mock_openai_completion
    ):
        with patch("app.routers.ocr._extractor") as mock_extractor:
            from app.models.ktp import KTPData
            mock_ktp = KTPData(
                nik="3201234567890001",
                nama="BUDI SANTOSO",
                jenis_kelamin="LAKI-LAKI",
            )
            mock_extractor.extract.return_value = (mock_ktp, "gpt-4o-2024-08-06")
            response = client.post(
                "/ocr/extract",
                files={"file": ("ktp.jpg", valid_jpeg_bytes, "image/jpeg")},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["nik"] == "3201234567890001"
        assert body["data"]["nama"] == "BUDI SANTOSO"
        assert body["model_used"] == "gpt-4o-2024-08-06"
        assert body["processing_time_ms"] is not None

    def test_rejects_unsupported_mime(self, client):
        response = client.post(
            "/ocr/extract",
            files={"file": ("doc.pdf", b"fake pdf content", "application/pdf")},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "INVALID_IMAGE"

    def test_rejects_oversized_file(self, client):
        large_bytes = b"x" * (6 * 1024 * 1024)  # 6 MB
        response = client.post(
            "/ocr/extract",
            files={"file": ("big.jpg", large_bytes, "image/jpeg")},
        )
        assert response.status_code == 413
        body = response.json()
        assert body["error_code"] == "IMAGE_TOO_LARGE"

    def test_rejects_corrupt_image(self, client):
        response = client.post(
            "/ocr/extract",
            files={"file": ("corrupt.jpg", b"ini bukan gambar valid", "image/jpeg")},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_IMAGE"

    def test_openai_rate_limit_returns_429(self, client, valid_jpeg_bytes):
        from app.exceptions import KTPExtractionError
        with patch("app.routers.ocr._extractor") as mock_extractor:
            mock_extractor.extract.side_effect = KTPExtractionError(
                "Rate limit", status_code=429
            )
            response = client.post(
                "/ocr/extract",
                files={"file": ("ktp.jpg", valid_jpeg_bytes, "image/jpeg")},
            )
        assert response.status_code == 429
        assert response.json()["error_code"] == "EXTRACTION_FAILED"

    def test_openai_unavailable_returns_503(self, client, valid_jpeg_bytes):
        from app.exceptions import KTPExtractionError
        with patch("app.routers.ocr._extractor") as mock_extractor:
            mock_extractor.extract.side_effect = KTPExtractionError(
                "Service unavailable", status_code=503
            )
            response = client.post(
                "/ocr/extract",
                files={"file": ("ktp.jpg", valid_jpeg_bytes, "image/jpeg")},
            )
        assert response.status_code == 503

    def test_png_file_accepted(self, client, valid_png_bytes):
        with patch("app.routers.ocr._extractor") as mock_extractor:
            from app.models.ktp import KTPData
            mock_extractor.extract.return_value = (KTPData(), "gpt-4o-2024-08-06")
            response = client.post(
                "/ocr/extract",
                files={"file": ("ktp.png", valid_png_bytes, "image/png")},
            )
        assert response.status_code == 200


class TestKTPDataValidators:
    def test_nik_valid_16_digit(self):
        from app.models.ktp import KTPData
        ktp = KTPData(nik="3201234567890001")
        assert ktp.nik == "3201234567890001"

    def test_nik_too_short_becomes_none(self):
        from app.models.ktp import KTPData
        ktp = KTPData(nik="123456789012345")  # 15 digit
        assert ktp.nik is None

    def test_nik_with_spaces_cleaned(self):
        from app.models.ktp import KTPData
        ktp = KTPData(nik="3201 2345 6789 0001")
        assert ktp.nik == "3201234567890001"

    def test_nik_with_letters_becomes_none(self):
        from app.models.ktp import KTPData
        ktp = KTPData(nik="320123456789000X")
        assert ktp.nik is None

    def test_gender_laki_normalized(self):
        from app.models.ktp import KTPData
        assert KTPData(jenis_kelamin="LAKI").jenis_kelamin == "LAKI-LAKI"
        assert KTPData(jenis_kelamin="L").jenis_kelamin == "LAKI-LAKI"
        assert KTPData(jenis_kelamin="laki-laki").jenis_kelamin == "LAKI-LAKI"

    def test_gender_perempuan_normalized(self):
        from app.models.ktp import KTPData
        assert KTPData(jenis_kelamin="P").jenis_kelamin == "PEREMPUAN"
        assert KTPData(jenis_kelamin="perempuan").jenis_kelamin == "PEREMPUAN"

    def test_blood_type_uppercased(self):
        from app.models.ktp import KTPData
        assert KTPData(golongan_darah="ab").golongan_darah == "AB"

    def test_all_fields_none_is_valid(self):
        from app.models.ktp import KTPData
        ktp = KTPData()
        assert ktp.nik is None
        assert ktp.nama is None
