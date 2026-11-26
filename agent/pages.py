import httpx
import pymupdf
from bs4 import BeautifulSoup

MAX_PAGE_CHARS = 40_000
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def make_web_client() -> httpx.Client:
    return httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})


def _page_text(url: str, response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if url.endswith(".pdf") or "application/pdf" in content_type:
        with pymupdf.open(stream=response.content, filetype="pdf") as doc:
            if not doc.is_pdf:
                raise pymupdf.FileDataError("body is not a PDF")
            return " ".join(str(page.get_text()) for page in doc)
    return BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)


def fetch_text(web: httpx.Client, url: str, allowed: list[str], find: str = "") -> str:
    if url not in allowed:
        return f"Rejected: {url} is not in the allowed sources."
    try:
        response = web.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"Error fetching {url}: {exc}"
    try:
        text = _page_text(url, response)
    except pymupdf.FileDataError as exc:
        return f"Error reading {url}: {exc}"
    index = text.find(find) if find else 0
    note = ""
    if index < 0:
        note = f"'{find}' not found; showing the start of the document.\n"
        index = 0
    start = max(index - 200, 0)
    return note + text[start : start + MAX_PAGE_CHARS]
