# import os
# from dotenv import load_dotenv
# from pydantic_settings import BaseSettings
#
# load_dotenv()
#
# DATABASE_URL = os.getenv("DATABASE_URL")
#
# if not DATABASE_URL:
#     raise RuntimeError("DATABASE_URL is not set")
#
# APP_ENV = os.getenv("APP_ENV", "development")
#
#
#
# class Settings(BaseSettings):
#     DATABASE_URL: str
#     # DIRECT_URL: str
#     CLOUD_DATABASE_URL: str
#     JWT_ALGORITHM: str = "RS256"
#     ACCESS_TOKEN_EXPIRE_DAYS: int = 3
#
# settings = Settings()

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str
    CLOUD_DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    # DIRECT_URL: str
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 3

    class Config:
        env_file = ".env"

settings = Settings()