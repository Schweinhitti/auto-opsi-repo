import json
from datetime import UTC, datetime, timedelta

from builder.health import evaluate_status


def _iso(delta_seconds):
    return (datetime.now(UTC) - timedelta(seconds=delta_seconds)).isoformat()


def test_builder_health_startup_grace():
    result = evaluate_status(
        {"state": "starting", "service_started_at": _iso(120)},
        freshness_seconds=3600,
        startup_grace_seconds=900,
    )
    assert result["state"] == "starting"
    assert result["health"] == "healthy"


def test_builder_health_running_state():
    result = evaluate_status(
        {"state": "running", "last_cycle_started_at": _iso(300)},
        freshness_seconds=3600,
        startup_grace_seconds=900,
    )
    assert result["state"] == "running"
    assert result["health"] == "healthy"


def test_builder_health_success_state():
    result = evaluate_status(
        {"state": "idle", "last_cycle_result": "success", "last_cycle_finished_at": _iso(600)},
        freshness_seconds=3600,
        startup_grace_seconds=900,
    )
    assert result["state"] == "success"
    assert result["health"] == "healthy"


def test_builder_health_failed_state():
    result = evaluate_status(
        {"state": "idle", "last_cycle_result": "failed", "last_cycle_finished_at": _iso(120)},
        freshness_seconds=3600,
        startup_grace_seconds=900,
    )
    assert result["state"] == "failed"
    assert result["health"] == "degraded"


def test_builder_health_stale_cycle():
    result = evaluate_status(
        {"state": "idle", "last_cycle_result": "success", "last_cycle_finished_at": _iso(7201)},
        freshness_seconds=3600,
        startup_grace_seconds=900,
    )
    assert result["state"] == "stale"
    assert result["health"] == "unhealthy"


def test_builder_health_status_file_contract(tmp_path):
    status = {
        "state": "idle",
        "last_cycle_result": "success",
        "last_cycle_finished_at": _iso(100),
        "update_interval_seconds": 21600,
    }
    path = tmp_path / "builder-status.json"
    path.write_text(json.dumps(status))
    loaded = json.loads(path.read_text())
    result = evaluate_status(loaded, freshness_seconds=43200, startup_grace_seconds=900)
    assert result["state"] == "success"
