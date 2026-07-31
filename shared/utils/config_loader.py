"""
Config Loader — Memuat konfigurasi dari config.yaml secara terpusat.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Default config path
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Muat konfigurasi dari file YAML.

    Urutan pencarian path:
    1. Argument path yang diberikan secara eksplisit
    2. Environment variable CONFIG_PATH
    3. Default: config/config.yaml

    Args:
        path: Path eksplisit ke file config (optional)

    Returns:
        Dict konfigurasi

    Raises:
        FileNotFoundError: Jika file config tidak ditemukan
    """
    # Import yaml di sini agar tidak wajib terinstall saat import module
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML diperlukan untuk load config. "
            "Install dengan: pip install pyyaml"
        )

    # Tentukan path
    if path:
        config_path = Path(path)
    elif os.environ.get("CONFIG_PATH"):
        config_path = Path(os.environ["CONFIG_PATH"])
    else:
        config_path = _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Config file tidak ditemukan: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info("Config loaded from: %s", config_path)
    return config


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Ambil nilai config dengan dot-notation.

    Args:
        config: Dict konfigurasi
        key_path: Path key dengan dot (e.g. 'data.start_date')
        default: Nilai default jika key tidak ditemukan

    Returns:
        Nilai config atau default
    """
    keys = key_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value
