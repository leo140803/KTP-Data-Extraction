import io
import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# Set env var sebelum import module yang trigger Settings()
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

from app.exceptions import KTPExtractionError
from app.models.ktp import KTPData
from app.services.ktp_extractor import KTPExtractor


def make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (100, 60), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def extractor():
    with patch("app.services.ktp_extractor.OpenAI"):
        return KTPExtractor()


class TestExtractSuccess:
    def test_returns_ktp_data_and_model(self, extractor, mock_ktp_data, mock_openai_completion):
        extractor._client.beta.chat.completions.parse.return_value = mock_openai_completion
        result, model = extractor.extract(make_jpeg_bytes())
        assert isinstance(result, KTPData)
        assert result.nik == "3201234567890001"
        assert result.nama == "BUDI SANTOSO"
        assert model == "gpt-4o-2024-08-06"

    def test_uses_high_detail(self, extractor, mock_openai_completion):
        extractor._client.beta.chat.completions.parse.return_value = mock_openai_completion
        extractor.extract(make_jpeg_bytes())
        call_kwargs = extractor._client.beta.chat.completions.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
        # Cek image_url detail=high ada di messages
        user_content = messages[1]["content"]
        image_part = next(p for p in user_content if p["type"] == "image_url")
        assert image_part["image_url"]["detail"] == "high"

    def test_temperature_is_zero(self, extractor, mock_openai_completion):
        extractor._client.beta.chat.completions.parse.return_value = mock_openai_completion
        extractor.extract(make_jpeg_bytes())
        call_kwargs = extractor._client.beta.chat.completions.parse.call_args
        assert call_kwargs.kwargs.get("temperature") == 0


class TestExtractErrors:
    def test_auth_error_raises_500(self, extractor):
        from openai import AuthenticationError
        extractor._client.beta.chat.completions.parse.side_effect = AuthenticationError(
            message="Unauthorized", response=MagicMock(status_code=401), body={}
        )
        with pytest.raises(KTPExtractionError) as exc_info:
            extractor.extract(make_jpeg_bytes())
        assert exc_info.value.status_code == 500

    def test_rate_limit_raises_429(self, extractor):
        from openai import RateLimitError
        extractor._client.beta.chat.completions.parse.side_effect = RateLimitError(
            message="Rate limit", response=MagicMock(status_code=429), body={}
        )
        with pytest.raises(KTPExtractionError) as exc_info:
            extractor.extract(make_jpeg_bytes())
        assert exc_info.value.status_code == 429

    def test_timeout_raises_503(self, extractor):
        from openai import APITimeoutError
        extractor._client.beta.chat.completions.parse.side_effect = APITimeoutError(
            request=MagicMock()
        )
        with pytest.raises(KTPExtractionError) as exc_info:
            extractor.extract(make_jpeg_bytes())
        assert exc_info.value.status_code == 503

    def test_parsed_none_raises_422(self, extractor):
        mock_msg = MagicMock()
        mock_msg.parsed = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        extractor._client.beta.chat.completions.parse.return_value = mock_completion

        with pytest.raises(KTPExtractionError) as exc_info:
            extractor.extract(make_jpeg_bytes())
        assert exc_info.value.status_code == 422
