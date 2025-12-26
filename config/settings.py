"""
OneDay.run Platform - Configuration Settings
Platforma LLM do automatycznej realizacji zamówień prototypowania
"""
from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """Główne ustawienia platformy"""
    
    # Application
    APP_NAME: str = "OneDay.run Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Environment
    APP_ENV: str = "development"
    LOG_LEVEL: str = "info"

    # Docker/host ports (optional, mainly for local dev tooling)
    APP_HOST_PORT: Optional[int] = None
    POSTGRES_HOST_PORT: Optional[int] = None
    REDIS_HOST_PORT: Optional[int] = None
    LITELLM_HOST_PORT: Optional[int] = None
    
    # LLM Configuration
    LLM_PROVIDER: str = "anthropic"  # anthropic | ollama
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    DEFAULT_MODEL: str = "anthropic/claude-opus-4-5-20251101"
    FALLBACK_MODEL: str = "anthropic/claude-sonnet-4-5-20250929"
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.7

    CORS_ALLOW_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"

    UI_ENABLE_STT: bool = True
    UI_ENABLE_TTS: bool = True

    # Ollama (local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "ollama/llama3.1:8b"
    
    # LiteLLM Proxy (optional)
    LITELLM_PROXY_URL: Optional[str] = None
    LITELLM_API_KEY: Optional[str] = None
    
    # GitHub Configuration
    GITHUB_TOKEN: str = ""
    GITHUB_ORG: str = "prototypowanie-pl"  # Domyślna organizacja
    GITHUB_DEFAULT_BRANCH: str = "main"
    
    # Deployment Platforms
    RAILWAY_TOKEN: Optional[str] = None
    VERCEL_TOKEN: Optional[str] = None
    RENDER_API_KEY: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "sqlite:///./oneday.db"
    REDIS_URL: Optional[str] = None
    
    # Session & WebSocket
    SESSION_TIMEOUT_MINUTES: int = 60
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # Component Library
    COMPONENTS_REPO: str = "prototypowanie-pl/components-library"
    TEMPLATES_REPO: str = "prototypowanie-pl/project-templates"
    
    # Pricing (in PLN)
    PRICING_TIERS: dict = {
        "1h": {"price": 150, "max_tokens": 50000, "max_files": 5},
        "8h": {"price": 1200, "max_tokens": 400000, "max_files": 20},
        "24h": {"price": 3000, "max_tokens": 1200000, "max_files": 50},
        "36h": {"price": 3600, "max_tokens": 1800000, "max_files": 75},
        "48h": {"price": 4800, "max_tokens": 2400000, "max_files": 100},
        "72h": {"price": 7200, "max_tokens": 3600000, "max_files": 150},
    }
    
    # Supported project types
    PROJECT_TYPES: List[str] = [
        "web_app",
        "api",
        "dashboard",
        "automation",
        "integration",
        "landing_page",
        "e_commerce",
        "mobile_pwa",
    ]
    
    # Supported tech stacks
    TECH_STACKS: dict = {
        "python_fastapi": {
            "name": "Python + FastAPI",
            "languages": ["python"],
            "frameworks": ["fastapi", "pydantic", "sqlalchemy"],
            "deployment": ["railway", "render", "vercel"],
        },
        "python_django": {
            "name": "Python + Django",
            "languages": ["python"],
            "frameworks": ["django", "django-rest-framework"],
            "deployment": ["railway", "render"],
        },
        "node_express": {
            "name": "Node.js + Express",
            "languages": ["javascript", "typescript"],
            "frameworks": ["express", "prisma"],
            "deployment": ["railway", "vercel", "render"],
        },
        "react_next": {
            "name": "React + Next.js",
            "languages": ["javascript", "typescript"],
            "frameworks": ["nextjs", "react", "tailwindcss"],
            "deployment": ["vercel", "railway"],
        },
        "vue_nuxt": {
            "name": "Vue + Nuxt",
            "languages": ["javascript", "typescript"],
            "frameworks": ["nuxt", "vue", "tailwindcss"],
            "deployment": ["vercel", "railway"],
        },
    }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


# Convenience export
settings = get_settings()
