import re
from urllib.parse import unquote, urljoin, urlparse


CONTACT_HOST_HINTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
}

CONTACT_PATH_HINTS = {
    "contact",
    "contact-us",
    "connect",
    "get-in-touch",
    "locations",
}

NOISY_PATH_PARTS = {
    "admin",
    "feed",
    "intent",
    "posts",
    "post",
    "search",
    "share",
    "sharer",
    "status",
    "statuses",
}

MEDIA_EXTENSIONS = (
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
)


def _tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) >= 2 and token not in {"vc", "llc", "inc", "the", "and"}
    }


def _compact(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _hostname(url):
    try:
        return (urlparse(url).hostname or "").lower().replace("www.", "")
    except ValueError:
        return ""


def _domain_tokens(url):
    host = _hostname(url)
    parts = host.split(".")

    if len(parts) >= 2:
        parts = parts[:-1]

    return _tokens(" ".join(parts))


def _is_directory_profile(website, source_url):
    website_host = _hostname(website)
    source_host = _hostname(source_url)
    path = urlparse(website or "").path.lower()

    return bool(
        website_host
        and website_host == source_host
        and any(part in path for part in ["/profile", "/profiles", "/investor"])
    )


def _normalize_url(raw_url, base_url=""):
    raw_url = unquote(str(raw_url or "").strip())
    raw_url = raw_url.rstrip(").,;]")

    if not raw_url:
        return ""

    if raw_url.startswith("mailto:"):
        if "@" not in raw_url:
            return ""
        return raw_url

    if re.match(r"^https?://", raw_url, re.IGNORECASE):
        return raw_url

    if base_url and raw_url.startswith("/"):
        return urljoin(base_url, raw_url)

    return ""


def _candidate_urls(markdown_content, base_url=""):
    patterns = [
        r"\[!\[[^\]]*\]\([^)]+\)\]\(([^)\s]+)\)",
        r"\[[^\]]*\]\(([^)\s]+)\)",
        r"href=[\"']([^\"']+)[\"']",
        r"(mailto:[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
        r"(https?://[^\s<>\"]+)",
    ]
    urls = []

    for pattern in patterns:
        for match in re.findall(pattern, markdown_content or "", flags=re.IGNORECASE):
            normalized = _normalize_url(match, base_url=base_url)

            if normalized:
                urls.append(normalized)

    return list(dict.fromkeys(urls))


def _looks_noisy_social(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    path_tokens = _tokens(parsed.path)
    query = parsed.query.lower()

    return bool(path_tokens & NOISY_PATH_PARTS or "share" in query)


def _social_path_matches_identity(url, firm_tokens, website_tokens):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    path_tokens = _tokens(parsed.path)
    compact_path = _compact(parsed.path)
    compact_firm = _compact(" ".join(firm_tokens))
    compact_website = _compact(" ".join(website_tokens))

    return bool(
        path_tokens & firm_tokens
        or path_tokens & website_tokens
        or (compact_firm and compact_firm in compact_path)
        or (compact_website and compact_website in compact_path)
    )


def _looks_like_firm_social_profile(url, firm_tokens, website_tokens):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    host = _hostname(url)
    path_parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if not any(host == domain or host.endswith(f".{domain}") for domain in CONTACT_HOST_HINTS):
        return False

    if _looks_noisy_social(url) or not path_parts:
        return False

    if not _social_path_matches_identity(url, firm_tokens, website_tokens):
        return False

    if "linkedin.com" in host:
        return path_parts[0].lower() in {"company", "school", "showcase"}

    if "facebook.com" in host or "instagram.com" in host:
        return len(path_parts) <= 2

    if "twitter.com" in host or host == "x.com" or host.endswith(".x.com"):
        return len(path_parts) == 1

    return False


def _is_media_url(url):
    try:
        path = urlparse(url).path.lower()
    except ValueError:
        return True

    return path.endswith(MEDIA_EXTENSIONS)


def _social_profile_matches(url, firm_tokens, website_tokens):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = _hostname(url)
    host_matches = any(host == domain or host.endswith(f".{domain}") for domain in CONTACT_HOST_HINTS)

    if not host_matches or _looks_noisy_social(url):
        return False

    path_parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if not path_parts:
        return False

    if "linkedin.com" in host and path_parts[0].lower() == "in":
        return False

    return _looks_like_firm_social_profile(url, firm_tokens, website_tokens)


def _email_matches(url, firm_tokens, website_tokens, directory_profile=False):
    email = url.replace("mailto:", "", 1).lower()
    domain = email.split("@")[-1]
    email_tokens = _tokens(email.replace("@", " ").replace(".", " "))
    domain_tokens = _tokens(domain.replace(".", " "))

    if directory_profile:
        return bool((email_tokens | domain_tokens) & firm_tokens)

    return bool((email_tokens | domain_tokens) & (firm_tokens | website_tokens))


def extract_contact_links_from_markdown(
    markdown_content,
    firm="",
    website="",
    source_url="",
):
    firm_tokens = _tokens(firm)
    website_tokens = _domain_tokens(website)
    directory_profile = _is_directory_profile(website, source_url)
    extracted = []

    for url in _candidate_urls(markdown_content, base_url=website or source_url):
        if _contact_link_allowed(
            url,
            firm_tokens=firm_tokens,
            website_tokens=website_tokens,
            website=website,
            directory_profile=directory_profile,
        ):
            extracted.append(url)

    return list(dict.fromkeys(extracted))


def _contact_link_allowed(
    url,
    firm_tokens,
    website_tokens,
    website="",
    directory_profile=False,
):
    host = _hostname(url)

    if _is_media_url(url):
        return False

    if url.startswith("mailto:"):
        return _email_matches(
            url,
            firm_tokens,
            website_tokens,
            directory_profile=directory_profile,
        )

    if _social_profile_matches(url, firm_tokens, website_tokens):
        return True

    if not directory_profile and _looks_like_firm_social_profile(url, firm_tokens, website_tokens):
        return True

    if not directory_profile and website and host == _hostname(website):
        path = urlparse(url).path.lower()
        path_parts = {
            part
            for part in re.split(r"[^a-z0-9-]+", path)
            if part
        }

        if path_parts & CONTACT_PATH_HINTS:
            return True

    return False


def filter_contact_links_for_firm(
    links,
    firm="",
    website="",
    source_url="",
):
    firm_tokens = _tokens(firm)
    website_tokens = _domain_tokens(website)
    directory_profile = _is_directory_profile(website, source_url)
    filtered = []

    for link in links or []:
        normalized = _normalize_url(link, base_url=website or source_url)

        if not normalized:
            continue

        if _contact_link_allowed(
            normalized,
            firm_tokens=firm_tokens,
            website_tokens=website_tokens,
            website=website,
            directory_profile=directory_profile,
        ):
            filtered.append(normalized)

    return list(dict.fromkeys(filtered))
