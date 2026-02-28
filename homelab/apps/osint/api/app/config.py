"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Platform configuration loaded from environment."""

    # --- Redis / Celery ---
    redis_url: str = "redis://osint-redis:6379/0"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://osint-neo4j:7687"
    neo4j_auth: str = "neo4j/changeme"

    # --- Meilisearch ---
    meili_url: str = "http://osint-meili:7700"
    meili_master_key: str = ""

    # --- Auth ---
    auth_header: str = "Remote-User"

    # --- GDPR ---
    default_ttl_days: int = 365

    # --- Tor ---
    tor_socks_proxy: str = "socks5://osint-tor:9050"

    @property
    def neo4j_user(self) -> str:
        return self.neo4j_auth.split("/")[0]

    @property
    def neo4j_password(self) -> str:
        return self.neo4j_auth.split("/", 1)[1]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
