import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .state import atomic_json, now


def _parse_timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def _age_seconds(value, reference):
    stamp = _parse_timestamp(value)
    if stamp is None:
        return None
    return max(0, int((reference - stamp).total_seconds()))


def health_defaults(interval_seconds):
    raw_freshness = os.getenv("BUILDER_FRESHNESS_SECONDS", "")
    if raw_freshness:
        freshness = int(raw_freshness)
    else:
        freshness = max(interval_seconds * 2, 3600)
    startup_grace = int(os.getenv("BUILDER_STARTUP_GRACE_SECONDS", "900"))
    if freshness < 60:
        raise ValueError("BUILDER_FRESHNESS_SECONDS must be >=60")
    if startup_grace < 60:
        raise ValueError("BUILDER_STARTUP_GRACE_SECONDS must be >=60")
    return freshness, startup_grace


def status_path(root):
    return Path(root) / "state/builder-status.json"


def update_status(root, **changes):
    path = status_path(root)
    data = {
        "schema_version": 1,
        "service_started_at": now(),
        "state": "starting",
        "last_transition_at": now(),
        "last_cycle_result": None,
        "last_cycle_started_at": None,
        "last_cycle_finished_at": None,
        "failed_items": 0,
        "warning_items": 0,
    }
    if path.exists():
        data.update(json.loads(path.read_text()))
    data.update(changes)
    if changes:
        data["last_transition_at"] = now()
    atomic_json(path, data)
    return data


def evaluate_status(data, *, reference=None, freshness_seconds, startup_grace_seconds):
    reference = reference or datetime.now(UTC)
    state = data.get("state", "starting")
    started_age = _age_seconds(data.get("service_started_at"), reference)
    cycle_age = _age_seconds(data.get("last_cycle_finished_at"), reference)
    running_age = _age_seconds(data.get("last_cycle_started_at"), reference)
    result = data.get("last_cycle_result")
    effective = state
    health = "healthy"
    reason = ""

    if state == "running":
        age = running_age if running_age is not None else started_age
        if age is not None and age > freshness_seconds:
            effective = "stale"
            health = "unhealthy"
            reason = "cycle appears stuck or not updating"
        else:
            reason = "cycle currently running"
    elif result == "success":
        if cycle_age is not None and cycle_age > freshness_seconds:
            effective = "stale"
            health = "unhealthy"
            reason = "last successful cycle is stale"
        else:
            effective = "success"
            reason = "last cycle succeeded"
    elif result == "failed":
        if cycle_age is not None and cycle_age > freshness_seconds:
            effective = "stale"
            health = "unhealthy"
            reason = "builder has not completed a fresh cycle"
        else:
            effective = "failed"
            health = "degraded"
            reason = "last cycle completed with failures"
    else:
        if started_age is not None and started_age > startup_grace_seconds:
            effective = "stale"
            health = "unhealthy"
            reason = "startup grace exceeded before first completed cycle"
        else:
            effective = "starting"
            reason = "waiting for first completed cycle"

    return {
        "state": effective,
        "health": health,
        "reason": reason,
        "freshness_seconds": freshness_seconds,
        "startup_grace_seconds": startup_grace_seconds,
        "last_cycle_result": result,
        "last_cycle_started_at": data.get("last_cycle_started_at"),
        "last_cycle_finished_at": data.get("last_cycle_finished_at"),
        "failed_items": data.get("failed_items", 0),
        "warning_items": data.get("warning_items", 0),
    }


def _load(root):
    path = status_path(root)
    if path.exists():
        return json.loads(path.read_text())
    return {}


def main():
    parser = argparse.ArgumentParser(description="Builder health/status contract")
    parser.add_argument("--root", default=os.getenv("REPO_ROOT", "/data"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = _load(args.root)
    interval = int(data.get("update_interval_seconds", os.getenv("UPDATE_INTERVAL_SECONDS", "21600")))
    freshness, startup_grace = health_defaults(interval)
    evaluated = evaluate_status(
        data,
        freshness_seconds=freshness,
        startup_grace_seconds=startup_grace,
    )
    if args.json:
        print(json.dumps(evaluated, indent=2, sort_keys=True))
    else:
        print(
            f"{evaluated['health']} ({evaluated['state']}): {evaluated['reason']}",
            flush=True,
        )
    if args.check:
        return int(evaluated["health"] == "unhealthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
