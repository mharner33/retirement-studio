import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "./data"))


def db_path() -> Path:
    return data_dir() / "studio.db"
