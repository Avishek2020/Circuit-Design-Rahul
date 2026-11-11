from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/coldchain"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    pgvector_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
