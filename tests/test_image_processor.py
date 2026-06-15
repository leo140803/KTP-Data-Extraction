import io

import pytest
from PIL import Image

from app.exceptions import ImageValidationError
from app.services.image_processor import ImagePreprocessor


@pytest.fixture
def processor():
    return ImagePreprocessor(max_width=1600, max_height=1000)


def make_jpeg(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_png_rgba(width: int, height: int) -> bytes:
    img = Image.new("RGBA", (width, height), color=(200, 200, 200, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestDecodeAndValidate:
    def test_rejects_invalid_bytes(self, processor):
        with pytest.raises(ImageValidationError):
            processor.preprocess(b"ini bukan gambar")

    def test_rejects_empty_bytes(self, processor):
        with pytest.raises(ImageValidationError):
            processor.preprocess(b"")

    def test_accepts_valid_jpeg(self, processor):
        result, mime = processor.preprocess(make_jpeg(100, 100))
        assert mime == "image/jpeg"
        assert result[:2] == b"\xff\xd8"  # JPEG magic bytes

    def test_accepts_valid_png(self, processor):
        result, mime = processor.preprocess(make_png_rgba(100, 100))
        assert mime == "image/jpeg"


class TestResize:
    def test_downscales_oversized_image(self, processor):
        large_jpeg = make_jpeg(3000, 2000)
        result, _ = processor.preprocess(large_jpeg)
        result_img = Image.open(io.BytesIO(result))
        assert result_img.width <= 1600
        assert result_img.height <= 1000

    def test_does_not_upscale_small_image(self, processor):
        small_jpeg = make_jpeg(400, 250)
        result, _ = processor.preprocess(small_jpeg)
        result_img = Image.open(io.BytesIO(result))
        # Ukuran tidak boleh lebih besar dari original
        assert result_img.width <= 400
        assert result_img.height <= 250

    def test_preserves_aspect_ratio(self, processor):
        # 3200 x 1000 → max_width=1600, harus jadi 1600 x 500
        wide_jpeg = make_jpeg(3200, 1000)
        result, _ = processor.preprocess(wide_jpeg)
        result_img = Image.open(io.BytesIO(result))
        # Rasio harus mendekati 3.2:1
        ratio = result_img.width / result_img.height
        assert abs(ratio - 3.2) < 0.1


class TestAlphaConversion:
    def test_rgba_converted_to_rgb(self, processor):
        png_bytes = make_png_rgba(100, 100)
        result, _ = processor.preprocess(png_bytes)
        result_img = Image.open(io.BytesIO(result))
        assert result_img.mode == "RGB"


class TestOutputFormat:
    def test_output_is_always_jpeg(self, processor):
        _, mime = processor.preprocess(make_jpeg(100, 100))
        assert mime == "image/jpeg"

    def test_output_bytes_start_with_jpeg_magic(self, processor):
        result, _ = processor.preprocess(make_jpeg(100, 100))
        assert result[:2] == b"\xff\xd8"
