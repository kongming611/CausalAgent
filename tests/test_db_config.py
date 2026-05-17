import importlib


def test_settings_uses_legacy_mysql_host_as_write_host(monkeypatch):
    monkeypatch.setenv("MYSQL_WRITE_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "")
    monkeypatch.delenv("MYSQL_REPLICATION_USER", raising=False)
    monkeypatch.delenv("MYSQL_REPLICATION_PASSWORD", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_USER", "app")
    monkeypatch.setenv("MYSQL_PASSWORD", "pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_WRITE_HOST == "legacy-mysql"
    assert settings.MYSQL_READ_HOSTS == []
    assert settings.MAX_UPLOAD_SIZE_BYTES == 20 * 1024 * 1024


def test_settings_parses_replica_hosts_and_upload_limit(monkeypatch):
    monkeypatch.delenv("MYSQL_REPLICATION_USER", raising=False)
    monkeypatch.delenv("MYSQL_REPLICATION_PASSWORD", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_WRITE_HOST", "mysql-primary")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "mysql-replica-a, mysql-replica-b")
    monkeypatch.setenv("MYSQL_USER", "app")
    monkeypatch.setenv("MYSQL_PASSWORD", "pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "7")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_WRITE_HOST == "mysql-primary"
    assert settings.MYSQL_READ_HOSTS == ["mysql-replica-a", "mysql-replica-b"]
    assert settings.MAX_UPLOAD_SIZE_BYTES == 7 * 1024 * 1024


def test_settings_reads_replication_credentials(monkeypatch):
    monkeypatch.setenv("MYSQL_WRITE_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "")
    monkeypatch.setenv("MYSQL_REPLICATION_USER", "replica")
    monkeypatch.setenv("MYSQL_REPLICATION_PASSWORD", "replica-secret")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_USER", "app")
    monkeypatch.setenv("MYSQL_PASSWORD", "pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_REPLICATION_USER == "replica"
    assert settings.MYSQL_REPLICATION_PASSWORD == "replica-secret"


def test_settings_prefers_split_mysql_credentials(monkeypatch):
    monkeypatch.setenv("MYSQL_WRITE_HOST", "mysql-primary")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "mysql-replica")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_USER", "legacy-app")
    monkeypatch.setenv("MYSQL_PASSWORD", "legacy-pw")
    monkeypatch.setenv("MYSQL_WRITE_USER", "writer")
    monkeypatch.setenv("MYSQL_WRITE_PASSWORD", "writer-pw")
    monkeypatch.setenv("MYSQL_READ_USER", "reader")
    monkeypatch.setenv("MYSQL_READ_PASSWORD", "reader-pw")
    monkeypatch.setenv("MYSQL_REPLICA_STATUS_USER", "replica-status")
    monkeypatch.setenv("MYSQL_REPLICA_STATUS_PASSWORD", "status-pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_WRITE_USER == "writer"
    assert settings.MYSQL_WRITE_PASSWORD == "writer-pw"
    assert settings.MYSQL_READ_USER == "reader"
    assert settings.MYSQL_READ_PASSWORD == "reader-pw"
    assert settings.MYSQL_REPLICA_STATUS_USER == "replica-status"
    assert settings.MYSQL_REPLICA_STATUS_PASSWORD == "status-pw"


def test_settings_accepts_split_credentials_without_legacy_mysql_user(monkeypatch):
    monkeypatch.setenv("MYSQL_USER", "")
    monkeypatch.setenv("MYSQL_PASSWORD", "")
    monkeypatch.setenv("MYSQL_WRITE_HOST", "mysql-primary")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "mysql-replica")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_WRITE_USER", "writer")
    monkeypatch.setenv("MYSQL_WRITE_PASSWORD", "writer-pw")
    monkeypatch.setenv("MYSQL_READ_USER", "reader")
    monkeypatch.setenv("MYSQL_READ_PASSWORD", "reader-pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_USER is None
    assert settings.MYSQL_PASSWORD is None
    assert settings.MYSQL_WRITE_USER == "writer"
    assert settings.MYSQL_READ_USER == "reader"


def test_settings_keeps_legacy_fallback_but_not_for_replica_status(monkeypatch):
    for key in [
        "MYSQL_WRITE_USER",
        "MYSQL_WRITE_PASSWORD",
        "MYSQL_READ_USER",
        "MYSQL_READ_PASSWORD",
        "MYSQL_REPLICA_STATUS_USER",
        "MYSQL_REPLICA_STATUS_PASSWORD",
        "MYSQL_REPLICATION_USER",
        "MYSQL_REPLICATION_PASSWORD",
    ]:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("MYSQL_WRITE_HOST", "mysql-primary")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "mysql-replica")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_USER", "legacy-app")
    monkeypatch.setenv("MYSQL_PASSWORD", "legacy-pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")

    settings_module = importlib.import_module("config.settings")
    settings = importlib.reload(settings_module).AppConfig()

    assert settings.MYSQL_WRITE_USER == "legacy-app"
    assert settings.MYSQL_WRITE_PASSWORD == "legacy-pw"
    assert settings.MYSQL_READ_USER == "legacy-app"
    assert settings.MYSQL_READ_PASSWORD == "legacy-pw"
    assert settings.MYSQL_REPLICA_STATUS_USER is None
    assert settings.MYSQL_REPLICA_STATUS_PASSWORD is None
