"""Konfiguracja testów pytest i fixture'y wspólne."""

import sys
from pathlib import Path

# Dodanie katalogu głównego projektu do ścieżki Pythona
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
