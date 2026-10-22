import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.ops.firebase_hosting import deployment_plan

SOURCE = Path(__file__).resolve().parents[3] / "deploy" / "firebase"


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    shutil.copytree(SOURCE, tmp_path / "firebase")
    return tmp_path / "firebase" / "firebase.json"


def update_hosting(config_file: Path, changes: dict[str, Any]) -> None:
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["hosting"].update(changes)
    config_file.write_text(json.dumps(config), encoding="utf-8")


def test_static_plan_has_no_side_effects(config_file: Path) -> None:
    result = deployment_plan(config_file)
    assert result["status"] == "passed"
    assert result["applied"] is False
    assert result["backendRewrites"] == result["cloudRunIamChanges"] == 0
    assert 0 < result["uploadBytes"] < 32 * 1024


@pytest.mark.parametrize("option", ["rewrites", "redirects"])
def test_dynamic_routes_rejected(config_file: Path, option: str) -> None:
    update_hosting(config_file, {option: [{"source": "**", "destination": "/"}]})
    with pytest.raises(ValueError, match="Unexpected Hosting"):
        deployment_plan(config_file)


@pytest.mark.parametrize("changes", [{"site": "foreign-project"}, {"public": "../../"}])
def test_wrong_target_rejected(config_file: Path, changes: dict[str, Any]) -> None:
    update_hosting(config_file, changes)
    with pytest.raises(ValueError, match="Unexpected site"):
        deployment_plan(config_file)


def test_sensitive_extra_file_rejected(config_file: Path) -> None:
    (config_file.parent / "public" / ".env").write_text("synthetic-only", encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed static files"):
        deployment_plan(config_file)


def test_weak_cache_headers_rejected(config_file: Path) -> None:
    update_hosting(config_file, {"headers": []})
    with pytest.raises(ValueError, match="Security headers"):
        deployment_plan(config_file)


def test_foreign_project_binding_rejected(config_file: Path) -> None:
    (config_file.parent / ".firebaserc").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Project binding"):
        deployment_plan(config_file)


def test_oversized_asset_rejected(config_file: Path) -> None:
    (config_file.parent / "public" / "styles.css").write_bytes(b"x" * 32769)
    with pytest.raises(ValueError, match="32 KiB"):
        deployment_plan(config_file)
