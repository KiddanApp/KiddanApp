import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GEMINI_API_KEY: str = ""
    MAX_HISTORY: int = 3
    MONGODB_URL: str = "mongodb://localhost:27017/punjabi_tutor"

settings = Settings()
