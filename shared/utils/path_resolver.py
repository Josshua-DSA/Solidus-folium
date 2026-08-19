"""
Path Resolver Module — Isolasi direktori kerja Folium Terminal.

Memastikan Folium Terminal dapat dipanggil dari mana saja (global CLI)
dengan auto-resolution direktori data & konfigurasi:
  - Mode Repo: Jika berjalan dari repo lokal, gunakan data/ & config/ lokal.
  - Mode Global: Jika dipanggil sebagai paket terinstal global via `folium`,
                 gunakan `~/.folium/` di home directory user.

Path Mappings:
  - Config: ~/.folium/config.yaml  (fallback: repo/config/config.yaml)
  - Data DB: ~/.folium/data/ihsg_trading.db  (fallback: repo/data/ihsg_trading.db)
  - Models: ~/.folium/artifacts/saved_models/ (fallback: repo/artifacts/saved_models/)
  - Registry: ~/.folium/artifacts/registry.db (fallback: repo/artifacts/registry.db)
  - Logs: ~/.folium/logs/ (fallback: repo/outputs/logs/)
"""
import os
import shutil
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Root folder repo (jika ada)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Home directory user (~/.folium)
_USER_FOLIUM_DIR = Path.home() / ".folium"


def get_folium_dir() -> Path:
    """
    Return root folder data Folium.
    Jika repo lokal memiliki folder `data/` yang valid, prioritaskan repo lokal.
    Jika tidak (terinstal global), gunakan `~/.folium/`.
    """
    local_data = _REPO_ROOT / "data"
    if local_data.exists() and (_REPO_ROOT / "config" / "config.yaml").exists():
        return _REPO_ROOT

    # Mode Terinstal Global: Buat ~/.folium/ jika belum ada
    _USER_FOLIUM_DIR.mkdir(parents=True, exist_ok=True)
    return _USER_FOLIUM_DIR


def get_config_path() -> str:
    """Return path ke config.yaml (auto-copy template jika di ~/.folium/)."""
    root = get_folium_dir()
    config_file = root / "config" / "config.yaml"

    if not config_file.exists():
        # Copy template dari repo ke ~/.folium/config/config.yaml
        template = _REPO_ROOT / "config" / "config.yaml"
        if template.exists():
            config_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template, config_file)
            logger.info("Copied config template to %s", config_file)

    return str(config_file)


def get_db_path(custom_path: Optional[str] = None) -> str:
    """Return absolute path ke SQLite database file."""
    if custom_path:
        return str(Path(custom_path).resolve())

    root = get_folium_dir()
    db_file = root / "data" / "ihsg_trading.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return str(db_file)


def get_artifacts_dir() -> str:
    """Return absolute path ke folder saved_models."""
    root = get_folium_dir()
    artifacts = root / "artifacts" / "saved_models"
    artifacts.mkdir(parents=True, exist_ok=True)
    return str(artifacts)


def get_registry_db_path() -> str:
    """Return absolute path ke registry.db."""
    root = get_folium_dir()
    registry_file = root / "artifacts" / "registry.db"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    return str(registry_file)


def get_logs_dir() -> str:
    """Return absolute path ke folder logs."""
    root = get_folium_dir()
    logs = root / "outputs" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return str(logs)
