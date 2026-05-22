from pathlib import Path


MIGRATIONS_DIR = Path("Database/migrations/versions")


def test_first_migration_is_schema_bootstrap():
    bootstrap = MIGRATIONS_DIR / "1a2b3c4d5e6f_create_core_schema.py"
    assert bootstrap.exists(), "空库初始化需要先有核心业务表基线迁移"


def test_checkpoints_migration_depends_on_schema_bootstrap():
    checkpoints = MIGRATIONS_DIR / "bae097eab4b3_add_checkpoints_and_checkpoint_writes_.py"
    text = checkpoints.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"' in text


def test_production_upgrade_preserves_sessions_fk_support_index():
    production = MIGRATIONS_DIR / "f6b8c9d0e1a2_db_production_upgrade.py"
    text = production.read_text(encoding="utf-8")
    assert '_create_index_if_missing("sessions", "idx_sessions_user_fk", "`user_id`")' in text
    assert text.index('_create_index_if_missing("sessions", "idx_sessions_user_fk", "`user_id`")') < text.index(
        'for table_name, index_name in ['
    )
