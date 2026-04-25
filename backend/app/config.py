from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
FRONTEND_DIR = ROOT_DIR / "frontend"
SECRET = os.environ.get("MANGA_TRACE_SECRET", "dev-secret-change-me")
RENDERER_VERSION = "manga-trace-web-mvp-0.1"
