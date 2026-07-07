"""Centralized application settings loaded from environment variables (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_name: str = "UPRVUNL CODSP Backend"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # CORS — comma-separated list of allowed frontend origins.
    # Example: ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    database_url: str = "postgresql+psycopg://codsp_user:change_me@localhost:5432/codsp_db"

    # Storage
    document_storage_path: str = "./storage/documents"
    document_max_upload_size_bytes: int = 35 * 1024 * 1024

    # Daily stock validation
    stock_reconciliation_tolerance_mt: float = 0.01

    # Optimization
    optimization_fallback_landed_cost: float = 0.0
    optimization_market_topup_multiplier: float = 1.20
    optimization_demand_horizon_days: int = 30

    # UPSLDC Scheduler (legacy ingestion config)
    upsldc_source_url: str = "https://upsldc.org/variable-cost"
    upsldc_max_pdfs_per_run: int = 10
    scheduler_enabled: bool = False
    scheduler_cron_hour: int = 6
    scheduler_cron_minute: int = 0
    scheduler_timezone: str = "Asia/Kolkata"
    scheduler_document_check_hour: int = 6
    scheduler_document_check_minute: int = 0

    # UPSLDC MOD Reports Monitor (Milestone 9B)
    upsldc_mod_reports_url: str = "https://www.upsldc.org/schmod"
    upsldc_monitor_enabled: bool = False
    upsldc_monitor_top_n: int = 10
    upsldc_monitor_timeout_seconds: int = 20
    upsldc_monitor_user_agent: str = "CODSP-UPSLDC-Monitor/1.0"
    upsldc_monitor_schedule_days: str = "2,16"
    upsldc_monitor_hour: int = 9
    upsldc_monitor_minute: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
