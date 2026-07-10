"""Tests for the `sdlc phases --preset` profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sdlc_cli import app
from sdlc_cli.phases import (
    LEAN_DISABLED_STAGES,
    default_config,
    preset_config,
    preset_names,
)

runner = CliRunner()


def test_preset_names() -> None:
    assert set(preset_names()) == {"full", "lean"}


def test_full_preset_equals_default() -> None:
    assert preset_config("full") == default_config()


def test_lean_preset_disables_expected_stages() -> None:
    config = preset_config("lean")
    stages = config["stages"]

    for stage_id in LEAN_DISABLED_STAGES:
        assert stages[stage_id]["enabled"] is False

    # Every other stage stays enabled.
    for stage_id, entry in stages.items():
        if stage_id not in LEAN_DISABLED_STAGES:
            assert entry["enabled"] is True


def test_lean_preset_preserves_subagent_flags() -> None:
    # Disabling a stage must not wipe its subagent map (so re-enabling restores it).
    config = preset_config("lean")
    security = config["stages"]["stage-security"]
    assert security["enabled"] is False
    assert security["subagents"]  # non-empty
    assert all(v is True for v in security["subagents"].values())


def test_unknown_preset_raises() -> None:
    with pytest.raises(ValueError):
        preset_config("bogus")


def test_cli_preset_lean(tmp_path: Path) -> None:
    init = runner.invoke(
        app,
        ["init", str(tmp_path), "--integration", "devin", "--non-interactive"],
    )
    assert init.exit_code == 0

    result = runner.invoke(app, ["phases", str(tmp_path), "--preset", "lean"])
    assert result.exit_code == 0

    config = json.loads((tmp_path / ".sdlc" / "phase-config.json").read_text())
    stages = config["stages"]
    for stage_id in LEAN_DISABLED_STAGES:
        assert stages[stage_id]["enabled"] is False
    assert stages["stage-development"]["enabled"] is True


def test_cli_preset_invalid(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["init", str(tmp_path), "--integration", "devin", "--non-interactive"],
    )
    result = runner.invoke(app, ["phases", str(tmp_path), "--preset", "bogus"])
    assert result.exit_code == 1


def test_cli_preset_full_then_reset(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["init", str(tmp_path), "--integration", "devin", "--non-interactive"],
    )
    runner.invoke(app, ["phases", str(tmp_path), "--preset", "lean"])
    # Reset restores all-enabled default.
    result = runner.invoke(app, ["phases", str(tmp_path), "--reset"])
    assert result.exit_code == 0
    config = json.loads((tmp_path / ".sdlc" / "phase-config.json").read_text())
    assert all(entry["enabled"] for entry in config["stages"].values())


def _init(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["init", str(tmp_path), "--integration", "devin", "--non-interactive"],
    )
    assert result.exit_code == 0


def test_disable_unknown_stage_errors_and_no_write(tmp_path: Path) -> None:
    _init(tmp_path)
    before = (tmp_path / ".sdlc" / "phase-config.json").read_text()

    # Display name / wrong casing is NOT a valid stage-id.
    result = runner.invoke(app, ["phases", str(tmp_path), "--disable", "DevOps"])
    assert result.exit_code == 1
    assert "Unknown stage-id" in result.output

    # Config must be untouched (no silent no-op write).
    assert (tmp_path / ".sdlc" / "phase-config.json").read_text() == before


def test_disable_valid_stage_id_succeeds(tmp_path: Path) -> None:
    _init(tmp_path)
    result = runner.invoke(app, ["phases", str(tmp_path), "--disable", "stage-devops"])
    assert result.exit_code == 0
    config = json.loads((tmp_path / ".sdlc" / "phase-config.json").read_text())
    assert config["stages"]["stage-devops"]["enabled"] is False


def test_bootstrap_cannot_be_disabled(tmp_path: Path) -> None:
    _init(tmp_path)
    result = runner.invoke(
        app, ["phases", str(tmp_path), "--disable", "stage-bootstrap"]
    )
    assert result.exit_code == 1
    assert "cannot be disabled" in result.output


def test_disable_unknown_subagent_errors(tmp_path: Path) -> None:
    _init(tmp_path)
    result = runner.invoke(
        app,
        ["phases", str(tmp_path), "--disable-sub", "stage-testing:sub-bogus"],
    )
    assert result.exit_code == 1
    assert "Unknown subagent" in result.output
