# app/tests/conftest.py
import sys, pathlib
from dotenv import load_dotenv

# Proje kökünü sys.path'e ekle (app/tests -> app -> KÖK: parents[2])
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# .env'yi yükle (DATABASE_URL vb.)
load_dotenv()