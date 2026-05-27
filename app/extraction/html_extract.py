from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.extraction.firecrawl_extract import IMPORTANT_SUBPAGES


def _page_to_text(url, html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    parts = [f"URL: {url}"]

    title = soup.find("title")
    if title and title.get_text(strip=True):
        parts.append(f"# {title.get_text(strip=True)}")

    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = heading.get_text(" ", strip=True)
        if text:
            parts.append(f"## {text}")

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        href = urljoin(url, link["href"])
        if text and href:
            parts.append(f"{text}: {href}")

    body_text = soup.get_text("\n", strip=True)
    if body_text:
        parts.append(body_text)

    return "\n".join(parts)


def extract_website_with_requests(base_url, timeout=15):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )

    extracted = []

    for path in IMPORTANT_SUBPAGES:
        url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))

        try:
            response = session.get(url, timeout=timeout)
            content_type = response.headers.get("content-type", "")

            if response.status_code >= 400 or "text/html" not in content_type:
                continue

            text = _page_to_text(url, response.text)

            if text:
                extracted.append(
                    f"\n\n====================\nURL: {url}\n====================\n\n{text}"
                )

        except requests.RequestException:
            continue

    if not extracted:
        return ""

    return "\n".join(extracted)
