# app/config.py
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    backend_name: str = "qa-backend"
    api_prefix: str = "/api"
    cors_origins: List[str] = ["http://localhost:5173"]

    class Config:
        env_prefix = "QA_"
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
