import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _prepare_helper_fixture(
    tmp_path: Path,
    *,
    compose_config: dict,
    chown_exit_code: int = 0,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    repo = tmp_path / "repo"
    helper_dir = repo / "helper"
    fakebin_dir = repo / "fakebin"
    helper_dir.mkdir(parents=True)
    fakebin_dir.mkdir()

    shutil.copy(ROOT / "helper/run.sh", helper_dir / "run.sh")
    shutil.copy(ROOT / ".env.example", repo / ".env.example")

    chown_args_file = repo / "chown-args.txt"
    _write_executable(
        fakebin_dir / "chown",
        """#!/bin/sh
set -eu
printf "%s" "$*" > "$FAKE_CHOWN_ARGS_FILE"
exit "${FAKE_CHOWN_EXIT_CODE:-0}"
""",
    )
    _write_executable(
        fakebin_dir / "docker",
        """#!/bin/sh
set -eu
if [ "$1" != "compose" ]; then
  exit 2
fi
shift
case "$1" in
  config)
    shift
    if [ "$1" = "--format" ] && [ "$2" = "json" ]; then
      printf "%s\\n" "$FAKE_COMPOSE_CONFIG_JSON"
      exit 0
    fi
    ;;
  up)
    exit 0
    ;;
  exec)
    exit 0
    ;;
  ps)
    printf "fake compose ps\\n"
    exit 0
    ;;
esac
exit 2
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fakebin_dir}:{env['PATH']}",
            "FAKE_COMPOSE_CONFIG_JSON": json.dumps(compose_config),
            "FAKE_CHOWN_ARGS_FILE": str(chown_args_file),
            "FAKE_CHOWN_EXIT_CODE": str(chown_exit_code),
        }
    )

    proc = subprocess.run(
        ["bash", str(helper_dir / "run.sh")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc, chown_args_file


def test_helper_run_uses_effective_compose_user_for_chown(tmp_path):
    proc, chown_args_file = _prepare_helper_fixture(
        tmp_path,
        compose_config={
            "services": {
                "repo-builder": {"user": "2000:2001"},
                "repo-web": {"ports": ["127.0.0.1:8088:80"]},
            }
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert chown_args_file.read_text() == "-R 2000:2001 repository state work"


def test_helper_run_prints_effective_compose_endpoint(tmp_path):
    proc, _ = _prepare_helper_fixture(
        tmp_path,
        compose_config={
            "services": {
                "repo-builder": {"user": "1000:1000"},
                "repo-web": {"ports": [{"host_ip": "127.0.0.1", "published": "37563", "target": 80}]},
            }
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert "http://127.0.0.1:37563" in proc.stdout


def test_helper_run_fails_when_chown_fails(tmp_path):
    proc, _ = _prepare_helper_fixture(
        tmp_path,
        compose_config={
            "services": {
                "repo-builder": {"user": "1000:1000"},
                "repo-web": {"ports": ["0.0.0.0:8088:80"]},
            }
        },
        chown_exit_code=1,
    )

    assert proc.returncode != 0
    assert "Failed to set ownership" in proc.stderr
