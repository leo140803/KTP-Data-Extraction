from typing import Optional
from pydantic import BaseModel
from app.models.ktp import KTPData


class OCRResponse(BaseModel):
    success: bool
    data: Optional[KTPData] = None
    message: str = "OK"
    model_used: Optional[str] = None
    processing_time_ms: Optional[float] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    detail: Optional[str] = None
