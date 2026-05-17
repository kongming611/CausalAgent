from pathlib import Path


def test_primary_semisync_settings_use_loose_prefix():
    text = Path("Database/mysql/conf/primary.cnf").read_text(encoding="utf-8")
    assert "loose-rpl_semi_sync_source_enabled=ON" in text
    assert "loose-rpl_semi_sync_source_timeout=1000" in text


def test_replica_semisync_settings_use_loose_prefix():
    text = Path("Database/mysql/conf/replica.cnf").read_text(encoding="utf-8")
    assert "loose-rpl_semi_sync_replica_enabled=ON" in text
    assert "read_only=ON" not in text
    assert "super_read_only=ON" not in text


def test_replica_init_script_temporarily_disables_read_only():
    text = Path("Database/mysql/init/replica/01-configure-replication.sh").read_text(encoding="utf-8")
    assert "SET GLOBAL super_read_only = OFF;" in text
    assert "SET GLOBAL read_only = OFF;" in text
    assert "SET GLOBAL read_only = ON;" in text
    assert "SET GLOBAL super_read_only = ON;" in text


def test_replica_service_does_not_bootstrap_app_database_or_user():
    text = Path("docker-compose.replica.yml").read_text(encoding="utf-8")
    replica_block = text.split("  mysql-replica:")[1].split("  app:")[0]
    assert "MYSQL_DATABASE:" not in replica_block
    assert "MYSQL_USER:" not in replica_block
    assert "MYSQL_PASSWORD:" not in replica_block


def test_app_service_receives_split_mysql_credentials():
    text = Path("docker-compose.replica.yml").read_text(encoding="utf-8")
    app_block = text.split("  app:")[1].split("networks:")[0]
    assert "MYSQL_WRITE_USER=${MYSQL_WRITE_USER:-${MYSQL_USER}}" in app_block
    assert "MYSQL_WRITE_PASSWORD=${MYSQL_WRITE_PASSWORD:-${MYSQL_PASSWORD}}" in app_block
    assert "MYSQL_READ_USER=${MYSQL_READ_USER:-${MYSQL_USER}}" in app_block
    assert "MYSQL_READ_PASSWORD=${MYSQL_READ_PASSWORD:-${MYSQL_PASSWORD}}" in app_block
    assert "MYSQL_REPLICA_STATUS_USER=${MYSQL_REPLICA_STATUS_USER:-}" in app_block
    assert "MYSQL_REPLICA_STATUS_PASSWORD=${MYSQL_REPLICA_STATUS_PASSWORD:-}" in app_block


def test_primary_service_receives_split_mysql_credentials_for_bootstrap():
    text = Path("docker-compose.replica.yml").read_text(encoding="utf-8")
    primary_block = text.split("  mysql-primary:")[1].split("  mysql-replica:")[0]
    assert "MYSQL_WRITE_USER: ${MYSQL_WRITE_USER:-${MYSQL_USER}}" in primary_block
    assert "MYSQL_WRITE_PASSWORD: ${MYSQL_WRITE_PASSWORD:-${MYSQL_PASSWORD}}" in primary_block
    assert "MYSQL_READ_USER: ${MYSQL_READ_USER:-${MYSQL_USER}}" in primary_block
    assert "MYSQL_READ_PASSWORD: ${MYSQL_READ_PASSWORD:-${MYSQL_PASSWORD}}" in primary_block
    assert "MYSQL_REPLICA_STATUS_USER: ${MYSQL_REPLICA_STATUS_USER:-}" in primary_block
    assert "MYSQL_REPLICA_STATUS_PASSWORD: ${MYSQL_REPLICA_STATUS_PASSWORD:-}" in primary_block


def test_primary_init_creates_app_read_and_replica_status_accounts():
    text = Path("Database/mysql/init/primary/01-create-replication-user.sh").read_text(
        encoding="utf-8"
    )
    assert "MYSQL_READ_USER" in text
    assert "GRANT SELECT ON" in text
    assert "MYSQL_REPLICA_STATUS_USER" in text
    assert "GRANT REPLICATION CLIENT ON *.*" in text


def test_primary_write_user_has_references_privilege_for_migrations():
    text = Path("Database/mysql/init/primary/01-create-replication-user.sh").read_text(
        encoding="utf-8"
    )
    assert "REFERENCES" in text
