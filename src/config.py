"""Configuration — settings from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", "postgresql://admin:88888888@localhost:5432/mysynapse"
    ))
    qdrant_url: str = field(default_factory=lambda: os.getenv(
        "QDRANT_URL", "http://localhost:6333"
    ))
    qdrant_collection: str = field(default_factory=lambda: os.getenv(
        "QDRANT_COLLECTION", "mysynapse_vectors"
    ))
    ollama_url: str = field(default_factory=lambda: os.getenv(
        "OLLAMA_URL", "http://localhost:11434"
    ))
    embedding_model: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_MODEL", "nomic-embed-text"
    ))
    embedding_dim: int = field(default_factory=lambda: int(os.getenv(
        "EMBEDDING_DIM", "768"
    )))
    embedding_timeout: int = field(default_factory=lambda: int(os.getenv(
        "EMBEDDING_TIMEOUT", "30"
    )))
    api_host: str = field(default_factory=lambda: os.getenv(
        "MYSYNAPSE_HOST", "0.0.0.0"
    ))
    api_port: int = field(default_factory=lambda: int(os.getenv(
        "MYSYNAPSE_PORT", "8420"
    )))
    log_level: str = field(default_factory=lambda: os.getenv(
        "LOG_LEVEL", "INFO"
    ))
    search_weights: list[float] = field(default_factory=lambda: [
        float(x) for x in os.getenv("SEARCH_WEIGHTS", "0.6,0.4").split(",")
    ])
    search_rrf_k: int = 60
    cache_ttl: int = field(default_factory=lambda: int(os.getenv(
        "CACHE_TTL", "300"
    )))
    cache_max_size: int = field(default_factory=lambda: int(os.getenv(
        "CACHE_MAX_SIZE", "1000"
    )))