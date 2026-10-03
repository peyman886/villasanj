"""Runtime configuration from the environment; ``.env`` in development. Secrets are SecretStr."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_AVALAI_BASE_URL = "https://api.avalai.ir/v1"
DEFAULT_PROJECT_BUDGET_USD = Decimal(30)


class LLMBudgetSettings(BaseModel):
    project_usd: Decimal = Field(default=DEFAULT_PROJECT_BUDGET_USD, gt=0)


class LLMSettings(BaseModel):
    provider: Literal["avalai", "fake", "offline"] = "fake"  # offline: cached answers only
    routing_file: str = "llm.toml"  # relative to config_dir
    models_file: str = "llm-models.json"  # relative to config_dir
    budget: LLMBudgetSettings = LLMBudgetSettings()


class CrawlSettings(BaseModel):
    contact: str | None = None
    mode: Literal["offline", "live"] = "offline"
    min_delay_seconds: float = Field(default=3.0, ge=3.0)  # ADR-0008 floor
    region_file: str = "region.toml"  # relative to config_dir
    bot_name: str = "VillasanjBot"
    bot_version: str = "0.1"

    def user_agent(self) -> str:
        contact = f"; contact: {self.contact}" if self.contact else ""
        return f"{self.bot_name}/{self.bot_version} (research prototype{contact})"


class DatabaseSettings(BaseModel):
    url: str = "postgresql+psycopg://villasanj:villasanj@localhost:5433/villasanj"
    pool_size: int = Field(default=5, ge=1)


class PricingSettings(BaseModel):
    offer_max_age_hours: float = Field(default=24.0, gt=0)  # older offers are flagged stale (M6)


class BlobSettings(BaseModel):
    root: Path = Path("../var/blobs")


class GeoSettings(BaseModel):
    """OSM data and the routing server (ADR-0013); ``infra/osm/prepare.sh`` fills ``osm_dir``."""

    osm_dir: Path = Path("../data/osm")
    osrm_url: str = "http://127.0.0.1:5050"

    @property
    def dataset(self) -> str:
        """The OSM snapshot the prepared files came from, e.g. "iran-260930"."""
        marker = self.osm_dir / "SNAPSHOT"
        return marker.read_text(encoding="utf-8").strip() if marker.exists() else "unknown"


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "console"] = "json"


class Settings(BaseSettings):
    """Paths default to the repository layout when commands run from ``backend/``."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    avalai_api_key: SecretStr | None = None
    avalai_base_url: str = DEFAULT_AVALAI_BASE_URL
    config_dir: Path = Path("../config")
    health_timeout_seconds: float = Field(default=5.0, gt=0)

    llm: LLMSettings = LLMSettings()
    crawl: CrawlSettings = CrawlSettings()
    database: DatabaseSettings = DatabaseSettings()
    blob: BlobSettings = BlobSettings()
    pricing: PricingSettings = PricingSettings()
    geo: GeoSettings = GeoSettings()
    logging: LoggingSettings = LoggingSettings()

    @property
    def routing_path(self) -> Path:
        return self.config_dir / self.llm.routing_file

    @property
    def scenarios_path(self) -> Path:
        return self.config_dir / "scenarios.toml"

    @property
    def fees_path(self) -> Path:
        return self.config_dir / "fees.toml"

    @property
    def gazetteer_path(self) -> Path:
        return self.config_dir / "gazetteer.toml"

    @property
    def features_path(self) -> Path:
        return self.config_dir / "features.toml"

    @property
    def routing_origin_path(self) -> Path:
        return self.config_dir / "routing.toml"

    @property
    def er_path(self) -> Path:
        return self.config_dir / "er.toml"

    @property
    def holidays_path(self) -> Path:
        return self.config_dir / "holidays.toml"

    @property
    def region_path(self) -> Path:
        return self.config_dir / self.crawl.region_file

    @property
    def models_path(self) -> Path:
        return self.config_dir / self.llm.models_file

    def secret_values(self) -> list[str]:
        """Values that must never appear in logs or error output."""
        return [self.avalai_api_key.get_secret_value()] if self.avalai_api_key else []
