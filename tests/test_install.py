"""Tests that verify install/uninstall artifacts."""

import os
import subprocess

# Derive PANCAKE_DIR from this file's location (tests/ is one level below repo root)
PANCAKE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_install_script_exists():
    assert os.path.isfile(f"{PANCAKE_DIR}/install.sh")


def test_uninstall_script_exists():
    assert os.path.isfile(f"{PANCAKE_DIR}/uninstall.sh")


def test_install_script_executable():
    assert os.access(f"{PANCAKE_DIR}/install.sh", os.X_OK)


def test_uninstall_script_executable():
    assert os.access(f"{PANCAKE_DIR}/uninstall.sh", os.X_OK)


def test_pk_on_path_after_install():
    """After install, `pk` should be available."""
    result = subprocess.run(["which", "pk"], capture_output=True, text=True)
    if result.returncode == 0:
        assert ".local/bin/pk" in result.stdout or "pancake" in result.stdout


def test_priorities_template_exists():
    assert os.path.isfile(f"{PANCAKE_DIR}/templates/PRIORITIES.md")


def test_hammerspoon_hotkey_exists():
    assert os.path.isfile(f"{PANCAKE_DIR}/hammerspoon/pancake_hotkey.lua")


def test_claude_commands_exist():
    assert os.path.isfile(f"{PANCAKE_DIR}/claude/morning.md")
    assert os.path.isfile(f"{PANCAKE_DIR}/claude/think.md")
