from pathlib import Path


ROOT = Path(".")


def test_analysis_jobs_migration_defines_queue_events_and_active_guard():
    migrations = list((ROOT / "Database/migrations/versions").glob("*analysis_jobs*.py"))
    assert migrations, "长任务队列需要独立 Alembic 迁移"

    text = migrations[0].read_text(encoding="utf-8")
    assert "CREATE TABLE analysis_jobs" in text
    assert "CREATE TABLE analysis_job_events" in text
    assert "active_session_key" in text
    assert "GENERATED ALWAYS" not in text
    assert "UNIQUE KEY uq_analysis_jobs_active_session" in text
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" in text
    assert "FOREIGN KEY (session_id) REFERENCES sessions(id)" in text
    assert "FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id)" in text
    assert "idx_analysis_jobs_status_created" in text
    assert "idx_analysis_job_events_job_id" in text


def test_database_readiness_requires_analysis_job_tables():
    text = (ROOT / "app/db.py").read_text(encoding="utf-8")
    assert '"analysis_jobs"' in text
    assert '"analysis_job_events"' in text


def test_graph_checkpointer_uses_write_credentials_not_legacy_user():
    text = (ROOT / "Agent/causal_agent/graph.py").read_text(encoding="utf-8")
    assert "'user': settings.MYSQL_WRITE_USER" in text
    assert "'password': settings.MYSQL_WRITE_PASSWORD" in text
    assert "'user': settings.MYSQL_USER" not in text
    assert "'password': settings.MYSQL_PASSWORD" not in text


def test_agent_routes_expose_job_endpoints_and_deprecate_old_stream():
    text = (ROOT / "app/agent/routes.py").read_text(encoding="utf-8")
    assert "@agent_bp.route('/agent/jobs', methods=['POST'])" in text
    assert "@agent_bp.route('/agent/jobs/<job_id>/events')" in text
    assert "analysis job API" in text


def test_frontend_uses_job_creation_and_eventsource():
    text = (ROOT / "app/static/js/script.js").read_text(encoding="utf-8")
    assert "fetch('/api/agent/jobs'" in text
    assert "new EventSource(" in text
    assert "Last-Event-ID" not in text


def test_docker_uses_gunicorn_web_entry_and_worker_service():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.replica.yml").read_text(encoding="utf-8")

    assert "gunicorn" in requirements.lower()
    assert "gunicorn" in dockerfile
    assert "worker:" in compose
    assert "python -m app.agent.worker" in compose


def test_session_delete_checks_active_analysis_jobs_before_deleting():
    text = (ROOT / "app/chat/routes.py").read_text(encoding="utf-8")
    assert "analysis_jobs" in text
    assert "queued', 'running" in text
    assert "当前会话仍有任务正在运行" in text


def test_worker_forces_logging_config_for_docker_logs():
    text = (ROOT / "app/agent/worker.py").read_text(encoding="utf-8")
    assert "logging.basicConfig(" in text
    assert "force=True" in text
