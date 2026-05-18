import importlib
import importlib.util
from pathlib import Path
import sys
import types


def _load_db_module(monkeypatch, *, include_status_credentials=True):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MYSQL_HOST", "legacy-mysql")
    monkeypatch.setenv("MYSQL_WRITE_HOST", "mysql-primary")
    monkeypatch.setenv("MYSQL_READ_HOSTS", "mysql-replica")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_USER", "legacy-app")
    monkeypatch.setenv("MYSQL_PASSWORD", "legacy-pw")
    monkeypatch.setenv("MYSQL_WRITE_USER", "writer")
    monkeypatch.setenv("MYSQL_WRITE_PASSWORD", "writer-pw")
    monkeypatch.setenv("MYSQL_READ_USER", "reader")
    monkeypatch.setenv("MYSQL_READ_PASSWORD", "reader-pw")
    monkeypatch.setenv("MYSQL_DATABASE", "causalchat")
    if include_status_credentials:
        monkeypatch.setenv("MYSQL_REPLICA_STATUS_USER", "replica-status")
        monkeypatch.setenv("MYSQL_REPLICA_STATUS_PASSWORD", "status-pw")
    else:
        monkeypatch.setenv("MYSQL_REPLICA_STATUS_USER", "")
        monkeypatch.setenv("MYSQL_REPLICA_STATUS_PASSWORD", "")

    mysql_package = types.ModuleType("mysql")
    connector_module = types.ModuleType("mysql.connector")

    class MySQLError(Exception):
        errno = None

    class Pool:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def get_connection(self):
            raise AssertionError("test did not provide a fake connection")

    connector_module.Error = MySQLError
    connector_module.errorcode = types.SimpleNamespace(
        ER_ACCESS_DENIED_ERROR=1045,
        ER_BAD_DB_ERROR=1049,
    )
    connector_module.pooling = types.SimpleNamespace(MySQLConnectionPool=Pool)
    mysql_package.connector = connector_module
    monkeypatch.setitem(sys.modules, "mysql", mysql_package)
    monkeypatch.setitem(sys.modules, "mysql.connector", connector_module)

    settings_module = importlib.import_module("config.settings")
    importlib.reload(settings_module)
    spec = importlib.util.spec_from_file_location(
        "app_db_under_test",
        Path("app/db.py").resolve(),
    )
    db_module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(db_module)
    db_module._write_pool = None
    db_module._read_pools = {}
    return db_module


def test_connection_configs_use_separate_credentials(monkeypatch):
    db = _load_db_module(monkeypatch)

    assert db.write_connection_config()["user"] == "writer"
    assert db.write_connection_config()["password"] == "writer-pw"
    assert db.read_connection_config("mysql-replica")["user"] == "reader"
    assert db.read_connection_config("mysql-replica")["password"] == "reader-pw"

    status_config = db.replica_status_connection_config("mysql-replica")
    assert status_config["user"] == "replica-status"
    assert status_config["password"] == "status-pw"
    assert "database" not in status_config


def test_missing_status_credentials_disable_replica_status_without_read_pool(monkeypatch):
    db = _load_db_module(monkeypatch, include_status_credentials=False)
    monkeypatch.setattr(
        db,
        "_get_read_pool",
        lambda host: (_ for _ in ()).throw(AssertionError("must not use business read pool")),
    )

    assert db.replica_status_connection_config("mysql-replica") is None
    assert db.get_replica_lag_seconds("mysql-replica") is None


def test_eventual_read_checks_status_before_business_replica_connection(monkeypatch):
    db = _load_db_module(monkeypatch)
    events = []
    read_conn = object()

    class StatusCursor:
        def execute(self, sql):
            events.append(f"status_sql:{sql}")

        def fetchone(self):
            return {
                "Replica_IO_Running": "Yes",
                "Replica_SQL_Running": "Yes",
                "Seconds_Behind_Source": 0,
            }

    class StatusConnection:
        def cursor(self, dictionary=False):
            events.append(f"status_cursor:{dictionary}")
            return StatusCursor()

        def close(self):
            events.append("status_closed")

    class ReadPool:
        def get_connection(self):
            events.append("read_connection")
            return read_conn

    def get_status_connection(host):
        events.append(f"status_connection:{host}")
        return StatusConnection()

    def get_read_pool(host):
        events.append(f"read_pool:{host}")
        return ReadPool()

    monkeypatch.setattr(db, "_get_replica_status_connection", get_status_connection, raising=False)
    monkeypatch.setattr(db, "_get_read_pool", get_read_pool)

    assert db.get_read_connection(consistency="eventual") is read_conn
    assert events == [
        "status_connection:mysql-replica",
        "status_cursor:True",
        "status_sql:SHOW REPLICA STATUS",
        "status_closed",
        "read_pool:mysql-replica",
        "read_connection",
    ]


def test_eventual_read_falls_back_to_primary_when_status_credentials_missing(monkeypatch):
    db = _load_db_module(monkeypatch, include_status_credentials=False)
    primary_read_conn = object()

    class PrimaryReadPool:
        def get_connection(self):
            return primary_read_conn

    def get_read_pool(host):
        assert host == db.settings.MYSQL_WRITE_HOST
        return PrimaryReadPool()

    monkeypatch.setattr(db, "_get_read_pool", get_read_pool)

    assert db.get_read_connection(consistency="eventual") is primary_read_conn


def test_eventual_read_falls_back_to_primary_when_status_connection_is_denied(monkeypatch):
    db = _load_db_module(monkeypatch)
    primary_read_conn = object()

    class PrimaryReadPool:
        def get_connection(self):
            return primary_read_conn

    class AccessDeniedError(db.mysql.connector.Error):
        errno = db.errorcode.ER_ACCESS_DENIED_ERROR

    def get_status_connection(host):
        raise AccessDeniedError("status access denied")

    def get_read_pool(host):
        assert host == db.settings.MYSQL_WRITE_HOST
        return PrimaryReadPool()

    monkeypatch.setattr(db, "_get_replica_status_connection", get_status_connection)
    monkeypatch.setattr(db, "_get_read_pool", get_read_pool)

    assert db.get_read_connection(consistency="eventual") is primary_read_conn
