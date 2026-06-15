import time

from fastapi import APIRouter, File, UploadFile

from app.config import settings
from app.exceptions import ImageTooLargeError, ImageValidationError
from app.models.responses import ErrorResponse, OCRResponse
from app.services.image_processor import ImagePreprocessor
from app.services.ktp_extractor import KTPExtractor

router = APIRouter(prefix="/ocr", tags=["OCR"])

_preprocessor = ImagePreprocessor(
    max_width=settings.preprocess_max_width,
    max_height=settings.preprocess_max_height,
)
_extractor = KTPExtractor()


@router.post(
    "/extract",
    response_model=OCRResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Gambar tidak valid atau tidak terbaca"},
        413: {"model": ErrorResponse, "description": "Ukuran gambar melebihi batas 5MB"},
        422: {"model": ErrorResponse, "description": "Field KTP tidak bisa diekstrak"},
        429: {"model": ErrorResponse, "description": "OpenAI rate limit"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "OpenAI tidak tersedia"},
    },
    summary="Ekstrak field KTP dari gambar",
    description=(
        "Upload foto KTP (JPEG, PNG, atau WebP). "
        "Mengembalikan semua field yang terbaca sebagai JSON terstruktur. "
        "Field yang tidak terbaca jelas dikembalikan sebagai null."
    ),
)
async def extract_ktp(
    file: UploadFile = File(..., description="File gambar KTP (JPEG/PNG/WebP, maks 5MB)"),
):
    start_time = time.perf_counter()

    # Validasi content-type sebelum baca bytes
    if file.content_type not in settings.allowed_content_types:
        raise ImageValidationError(
            f"Tipe file tidak didukung: '{file.content_type}'. "
            f"Yang diterima: {', '.join(settings.allowed_content_types)}."
        )

    # Baca bytes dengan size guard
    raw_bytes = await file.read()
    if len(raw_bytes) > settings.max_image_size_bytes:
        raise ImageTooLargeError()

    # Preprocessing gambar
    processed_bytes, mime_type = _preprocessor.preprocess(raw_bytes)

    # Ekstraksi dengan OpenAI Vision
    ktp_data, model_used = _extractor.extract(processed_bytes, mime_type)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return OCRResponse(
        success=True,
        data=ktp_data,
        model_used=model_used,
        processing_time_ms=round(elapsed_ms, 2),
    )
