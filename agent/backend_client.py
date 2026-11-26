import os

import httpx
from dotenv import load_dotenv


def make_client() -> httpx.Client:
    load_dotenv()
    return httpx.Client(
        base_url=os.environ.get("BACKEND_URL", "http://localhost:8000"), timeout=60
    )
