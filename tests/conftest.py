import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.models.ktp import KTPData


@pytest.fixture(scope="session")
def app():
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
    from app.main import create_app
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_ktp_data():
    return KTPData(
        provinsi="JAWA BARAT",
        kota_kabupaten="KOTA BANDUNG",
        nik="3201234567890001",
        nama="BUDI SANTOSO",
        tempat_lahir="BANDUNG",
        tanggal_lahir="15-03-1990",
        jenis_kelamin="LAKI-LAKI",
        golongan_darah="A",
        alamat="JL. MERDEKA NO. 10",
        rt_rw="003/007",
        kel_desa="SUKAJADI",
        kecamatan="SUKAJADI",
        agama="ISLAM",
        status_perkawinan="BELUM KAWIN",
        pekerjaan="KARYAWAN SWASTA",
        kewarganegaraan="WNI",
        berlaku_hingga="SEUMUR HIDUP",
    )


@pytest.fixture
def mock_openai_completion(mock_ktp_data):
    mock_msg = MagicMock()
    mock_msg.parsed = mock_ktp_data
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.model = "gpt-4o-2024-08-06"
    return mock_completion


@pytest.fixture
def valid_jpeg_bytes():
    img = Image.new("RGB", (200, 120), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def valid_png_bytes():
    img = Image.new("RGBA", (200, 120), color=(240, 240, 240, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
