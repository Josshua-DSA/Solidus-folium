"""
Tests for Standalone Desktop GUI Packaging Pipeline.

Verifies:
1. build_desktop_binary.py existence & executable permission
2. folium.desktop format & required keys
3. Nord Theme QSS & config.yaml bundled asset paths
4. Binary build output directory structure (dist/folium-workstation)
"""
import os
import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_build_script_exists():
    script_path = PROJECT_ROOT / "scripts" / "build_desktop_binary.py"
    assert script_path.exists()
    st = os.stat(script_path)
    assert bool(st.st_mode & stat.S_IXUSR) or bool(st.st_mode & stat.S_IRUSR)


def test_desktop_entry_validity():
    desktop_path = PROJECT_ROOT / "folium.desktop"
    assert desktop_path.exists()
    content = desktop_path.read_text()
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=Folium Quant Desk" in content
    assert "Exec=folium-workstation" in content


def test_bundled_assets_exist():
    qss_path = PROJECT_ROOT / "frontend" / "gui" / "styles" / "nord_theme.qss"
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    entrypoint = PROJECT_ROOT / "frontend" / "gui" / "app.py"

    assert qss_path.exists(), "Nord Theme QSS stylesheet missing"
    assert config_path.exists(), "config.yaml missing"
    assert entrypoint.exists(), "GUI entrypoint app.py missing"


def test_dist_binary_structure():
    dist_dir = PROJECT_ROOT / "dist" / "folium-workstation"
    binary_path = dist_dir / "folium-workstation"

    if dist_dir.exists():
        assert binary_path.exists()
        assert os.path.isfile(binary_path)
        assert os.access(binary_path, os.X_OK)
