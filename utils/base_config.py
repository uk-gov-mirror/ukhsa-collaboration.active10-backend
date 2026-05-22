import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    app_version: str = "dev"
    app_code_commit_hash: str = "dev"

    identity_broker_jwks_uri: str
    identity_broker_userinfo_uri: str
    identity_broker_issuer: str
    api_jwt_audience: str
    debug: bool = False
    db_host: str
    db_port: str
    db_user: str
    db_pass: str
    db_name: str
    app_uri: str
    gojauntly_key_id: str
    gojauntly_private_key: str
    gojauntly_issuer_id: str
    aws_sqs_queue_url: str
    aws_sqs_activities_migrations_queue_url: str
    aws_sns_activity_topic_arn: str
    aws_sns_activities_migration_topic_arn: str
    sendgrid_webhook_public_key: str
    email_hash_secret: str
    # Extra allowed for adding AWS_ local dummy secrets in the .env file
    model_config = SettingsConfigDict(
        env_file=(".env", "tests/tests.env"),
        env_file_encoding="utf-8",
        extra="allow",
    )


config = Config()


logger = logging.getLogger("Application-Logs")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
