import io
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.exceptions import ImageValidationError


class ImagePreprocessor:
    """
    Stateless image preprocessing pipeline.
    Semua operasi in-memory (bytes in, bytes out). Tidak ada disk I/O.
    """

    SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}

    def __init__(self, max_width: int = 1600, max_height: int = 1000):
        self.max_width = max_width
        self.max_height = max_height

    def preprocess(self, image_bytes: bytes) -> Tuple[bytes, str]:
        """
        Entry point utama. Mengembalikan (jpeg_bytes, mime_type).
        Pipeline: decode → to_rgb → resize → deskew → enhance → encode
        """
        img = self._decode_and_validate(image_bytes)
        img = self._convert_to_rgb(img)
        img = self._resize_if_needed(img)
        img = self._deskew(img)
        img = self._enhance_for_ocr(img)
        return self._encode_to_jpeg(img), "image/jpeg"

    def _decode_and_validate(self, image_bytes: bytes) -> Image.Image:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
        except Exception as e:
            raise ImageValidationError(f"Tidak bisa membaca file gambar: {e}")

        # Re-open setelah verify() karena verify() exhausts the file object
        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ImageValidationError(f"Tidak bisa membuka gambar: {e}")

        if img.format not in self.SUPPORTED_FORMATS:
            raise ImageValidationError(
                f"Format gambar tidak didukung: {img.format}. "
                f"Format yang diterima: JPEG, PNG, WEBP."
            )
        return img

    def _convert_to_rgb(self, img: Image.Image) -> Image.Image:
        if img.mode == "RGB":
            return img
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            alpha = img.split()[-1]
            background.paste(img, mask=alpha)
            return background
        return img.convert("RGB")

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        if w <= self.max_width and h <= self.max_height:
            return img
        ratio = min(self.max_width / w, self.max_height / h)
        new_size = (int(w * ratio), int(h * ratio))
        return img.resize(new_size, Image.LANCZOS)

    def _deskew(self, img: Image.Image) -> Image.Image:
        """
        Koreksi rotasi kecil menggunakan Hough line detection.
        Hanya koreksi ≤ 15 derajat. Fail-safe: kembalikan original jika error.
        """
        try:
            cv_img = np.array(img)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

            if lines is None:
                return img

            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = (theta * 180 / np.pi) - 90
                if abs(angle) <= 15:
                    angles.append(angle)

            if not angles:
                return img

            median_angle = float(np.median(angles))
            if abs(median_angle) < 0.5:
                return img

            return img.rotate(-median_angle, expand=True, fillcolor=(255, 255, 255))
        except Exception:
            return img

    def _enhance_for_ocr(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        return img

    def _encode_to_jpeg(self, img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        return buf.getvalue()
