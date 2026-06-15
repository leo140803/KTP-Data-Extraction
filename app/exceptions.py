from fastapi import Request
from fastapi.responses import JSONResponse


class ImageValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ImageTooLargeError(Exception):
    pass


class KTPExtractionError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def image_validation_handler(request: Request, exc: ImageValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error_code": "INVALID_IMAGE",
            "message": exc.message,
        },
    )


async def image_too_large_handler(request: Request, exc: ImageTooLargeError):
    from app.config import settings

    max_mb = settings.max_image_size_bytes // (1024 * 1024)
    return JSONResponse(
        status_code=413,
        content={
            "success": False,
            "error_code": "IMAGE_TOO_LARGE",
            "message": f"Image exceeds {max_mb}MB limit.",
        },
    )


async def ktp_extraction_handler(request: Request, exc: KTPExtractionError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": "EXTRACTION_FAILED",
            "message": exc.message,
        },
    )
