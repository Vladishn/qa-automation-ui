# app/config.py
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    backend_name: str = "qa-backend"
    api_prefix: str = "/api"
    cors_origins: List[str] = ["http://localhost:5173"]
    quickset_steps_dir: str = Field(
        default="artifacts/quickset_steps",
        description="Relative path to QuickSet step logs",
        env="QUICKSET_STEPS_DIR",
    )

    class Config:
        env_prefix = "QA_"
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
