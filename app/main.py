import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import (
    ImageTooLargeError,
    ImageValidationError,
    KTPExtractionError,
    image_too_large_handler,
    image_validation_handler,
    ktp_extraction_handler,
)
from app.routers import ocr

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"KTP OCR API starting. Model: {settings.openai_model}")
    yield
    logger.info("KTP OCR API shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="KTP OCR API",
        description=(
            "REST API untuk membaca foto KTP Indonesia dan mengekstrak semua field "
            "sebagai JSON terstruktur menggunakan GPT-4o Vision."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ImageValidationError, image_validation_handler)
    app.add_exception_handler(ImageTooLargeError, image_too_large_handler)
    app.add_exception_handler(KTPExtractionError, ktp_extraction_handler)

    app.include_router(ocr.router)

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health():
        return {"status": "ok", "model": settings.openai_model}

    return app


app = create_app()
