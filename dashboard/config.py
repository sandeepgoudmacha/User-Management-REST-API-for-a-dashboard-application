"""Configuration settings for the Brandmark API."""

from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = "Brandmark API"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Development Configuration
    dev_mode: bool = False
    mock_external_apis: bool = False
    
    # Database Configuration
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/brandmark"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # API Keys and Authentication
    secret_key: str = "dev-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # External API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    whois_api_key: Optional[str] = None
    namecheap_api_key: Optional[str] = None
    namecheap_api_user: Optional[str] = None
    godaddy_api_key: Optional[str] = None
    godaddy_api_secret: Optional[str] = None
    uspto_api_key: Optional[str] = None
    tmview_api_key: Optional[str] = None
    wipo_api_key: Optional[str] = None
    github_token: Optional[str] = None
    crunchbase_api_key: Optional[str] = None

    # Email Configuration
    sendgrid_api_key: Optional[str] = None
    from_email: Optional[str] = None
    admin_email: Optional[str] = None
    
    # Rate Limiting Configuration
    default_rate_limit: int = 100  # requests per hour
    
    # Provider Configuration
    enabled_providers: str = "domains,social,app_stores,package_registries,dev_platforms"
    
    # Cache Configuration
    cache_ttl_availability: int = 300  # 5 minutes
    cache_ttl_suggestions: int = 3600  # 1 hour
    cache_ttl_similar_names: int = 1800  # 30 minutes

    # AI Provider Configuration
    preferred_ai_provider: str = "anthropic_claude"  # Default AI provider
    ai_analysis_timeout: int = 30  # seconds
    ai_cache_ttl: int = 86400  # 24 hours for brand intelligence analysis

    # HTTP Timeout Configuration (seconds)
    http_timeout_default: float = 2.0  # Default HTTP timeout for all providers
    http_timeout_social: float = 2.0   # Social media providers
    http_timeout_domains: float = 5.0  # Domain WHOIS checks (need more time for real APIs)
    http_timeout_app_stores: float = 3.0  # App store APIs
    http_timeout_dev_platforms: float = 3.0  # GitHub, npm, etc.

    # Overall Request Timeouts
    provider_check_timeout: float = 5.0  # Individual provider timeout (increased for domains)
    total_request_timeout: float = 10.0  # Total request timeout for all providers
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @validator("database_url", pre=True)
    def validate_database_url(cls, v):
        if not v.startswith(("postgresql://", "postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError("Database URL must be PostgreSQL or SQLite (for testing)")
        return v

    @property
    def enabled_providers_list(self) -> List[str]:
        """Get enabled providers as a list."""
        if not self.enabled_providers.strip():
            return ["domains", "social", "app_stores", "package_registries", "dev_platforms"]
        return [provider.strip() for provider in self.enabled_providers.split(',') if provider.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Provider-specific rate limits (requests, seconds)
PROVIDER_RATE_LIMITS = {
    'instagram': (1, 1),          # 1 request per 1 second
    'twitter': (15, 900),         # 15 requests per 15 minutes
    'github': (5000, 3600),       # 5000 requests per hour
    'npm': (100, 60),             # 100 requests per minute
    'pypi': (60, 60),             # 60 requests per minute
    'chrome_webstore': (5, 60),   # 5 requests per minute
    'app_store_search': (20, 60), # 20 requests per minute
    'google_play_search': (10, 60), # 10 requests per minute
    'whois_api': (10, 60),        # 10 requests per minute
    'namecheap_api': (100, 3600), # 100 requests per hour
    'godaddy_api': (50, 60),      # 50 requests per minute
}

# API Key plan limits
PLAN_LIMITS = {
    'free': {'requests_per_hour': 100, 'suggestions_per_day': 20},
    'starter': {'requests_per_hour': 1000, 'suggestions_per_day': 200},
    'pro': {'requests_per_hour': 10000, 'suggestions_per_day': 1000},
}
