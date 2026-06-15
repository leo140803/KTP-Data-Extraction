from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o")
    openai_timeout: float = Field(default=60.0)
    openai_max_retries: int = Field(default=2)

    max_image_size_bytes: int = Field(default=5 * 1024 * 1024)
    allowed_content_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp"]
    )
    preprocess_max_width: int = Field(default=1600)
    preprocess_max_height: int = Field(default=1000)

    log_level: str = Field(default="INFO")


settings = Settings()
