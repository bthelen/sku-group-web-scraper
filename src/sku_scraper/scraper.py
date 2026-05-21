import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cloud.google.com"
INDEX_PATH = "/skus/sku-groups"
INDEX_URL = BASE_URL + INDEX_PATH
ALLOWED_URL_PREFIX = BASE_URL + INDEX_PATH + "/"

SKU_ID_RE = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

REQUEST_TIMEOUT = 30


def validate_slug(slug: str) -> str:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid SKU group slug {slug!r}. "
            "Slugs must be lowercase alphanumeric with hyphens (e.g. 'bigquery')."
        )
    return slug


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "sku-group-scraper/0.1 (github.com/bthelen/sku-group-web-scraper)"}
    )
    return session


def fetch_sku_groups(session: requests.Session) -> dict[str, str]:
    """Return {slug: full_url} for every SKU group listed on the index page."""
    response = session.get(INDEX_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    groups: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"]
        if href.startswith(INDEX_PATH + "/"):
            slug = href.removeprefix(INDEX_PATH + "/").rstrip("/")
            if slug and SLUG_RE.match(slug):
                groups[slug] = urljoin(BASE_URL, href)
    return groups


def fetch_sku_ids(session: requests.Session, url: str) -> list[str]:
    """Return a deduplicated, order-preserving list of SKU IDs from a group page."""
    if not url.startswith(ALLOWED_URL_PREFIX):
        raise ValueError(
            f"URL {url!r} is not an allowed SKU group URL. "
            f"Must start with {ALLOWED_URL_PREFIX!r}."
        )
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    seen: set[str] = set()
    sku_ids: list[str] = []
    for anchor in soup.find_all("a"):
        text = anchor.get_text(strip=True)
        if SKU_ID_RE.match(text) and text not in seen:
            seen.add(text)
            sku_ids.append(text)
    return sku_ids
