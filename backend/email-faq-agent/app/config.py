from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_use_starttls: bool = True
    smtp_from_email: str = "noreply@example.com"
    smtp_from_name: str = "Email Agent"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_email_topic: str = "email-jobs"
    kafka_dead_letter_topic: str = "email-jobs-dlq"
    kafka_consumer_group: str = "email-agent-group"

    # Agent
    max_retries: int = 3
    auto_queue_threshold_bytes: int = 1024  # payload size threshold for auto mode

    # Gemini
    gemini_api_key: str = ""

    # App
    log_level: str = "INFO"
    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
