#!/usr/bin/env python3
"""
Pocket Option Robot v2.0 — Запуск GUI.

Интерфейс в стиле расширения с интеграцией BinaryOptionsToolsV2.
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.runtime import load_runtime_config
from ui.app import run_gui


if __name__ == "__main__":
    config = load_runtime_config()
    run_gui(ssid=config.demo_ssid)
