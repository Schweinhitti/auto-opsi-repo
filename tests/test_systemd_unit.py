from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_systemd_service_uses_environment_configuration():
    """Allow compose location overrides without editing the service unit."""
    content = (ROOT / "systemd/opsi-local-auto-update.service").read_text()
    assert "WorkingDirectory=" not in content
    assert "EnvironmentFile=-/etc/default/opsi-local-auto-update" in content
    assert "Environment=OPSI_COMPOSE_DIR=/opt/opsi/opsi-docker/opsi-server" in content
    assert "Environment=OPSI_COMPOSE_SERVICE=opsi-server" in content


def test_systemd_service_validates_config_before_import():
    """Fail clearly when compose directory or service configuration is invalid."""
    content = (ROOT / "systemd/opsi-local-auto-update.service").read_text()
    assert 'if [ ! -d "$OPSI_COMPOSE_DIR" ]' in content
    assert "OPSI_COMPOSE_DIR does not exist" in content
    assert 'docker compose config --services | grep -Fxq "$OPSI_COMPOSE_SERVICE"' in content
    assert "OPSI_COMPOSE_SERVICE not found in compose project" in content
    assert 'docker compose exec -T "$OPSI_COMPOSE_SERVICE" opsi-package-updater' in content


def test_integration_doc_covers_unit_verification_and_failure_check():
    """Document one config location and verification/failure validation commands."""
    content = (ROOT / "docs/INTEGRATION.md").read_text()
    assert "/etc/default/opsi-local-auto-update" in content
    assert "systemd-analyze verify /etc/systemd/system/opsi-local-auto-update.service" in content
    assert "OPSI_COMPOSE_SERVICE=does-not-exist" in content
