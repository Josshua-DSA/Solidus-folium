"""
Tests for shared/utils/path_resolver.py — Path isolation and workspace auto-resolution.
"""
from pathlib import Path
from shared.utils.path_resolver import (
    get_folium_dir,
    get_config_path,
    get_db_path,
    get_artifacts_dir,
    get_registry_db_path,
    get_logs_dir,
)


def test_path_resolver_repo_mode():
    root = get_folium_dir()
    assert root.exists()

    config_path = get_config_path()
    assert config_path.endswith("config.yaml")

    db_path = get_db_path()
    assert db_path.endswith("ihsg_trading.db")

    art_dir = get_artifacts_dir()
    assert art_dir.endswith("saved_models")

    reg_db = get_registry_db_path()
    assert reg_db.endswith("registry.db")

    logs_dir = get_logs_dir()
    assert logs_dir.endswith("logs")


def test_path_resolver_custom_override():
    custom = get_db_path("/tmp/test_custom.db")
    assert custom == "/tmp/test_custom.db"
