"""
Output formatter: renders a structured investor dict as clean terminal output.
Uses ASCII-safe characters for Windows console compatibility.
"""

import sys

# Max portfolio companies shown before truncation notice
MAX_PORTFOLIO_DISPLAY = 8
# Max partners shown
MAX_PARTNERS_DISPLAY = 6
# Confidence score maximum (matches calculate_confidence_score() in run_pipeline.py)
MAX_CONFIDENCE = 19

_SEP_HEAVY = "=" * 62
_SEP_LIGHT = "-" * 62


def _safe(text: str) -> str:
    """Encode to console charset safely, replacing unencodable chars."""
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


def _confidence_bar(score: int, max_score: int = MAX_CONFIDENCE) -> str:
    """Render a compact ASCII progress bar for the confidence score."""
    filled = round((score / max_score) * 20)
    bar = "#" * filled + "." * (20 - filled)
    pct = round((score / max_score) * 100)
    return f"[{bar}] {score}/{max_score}  ({pct}%)"


def _section_header(label: str) -> str:
    return f"\n  [{label}]"


def _bullet(text: str) -> str:
    return f"    * {text}"


def _data_quality_indicator(investor: dict) -> str:
    """Generate a visual indicator of data quality/completeness."""
    quality = investor.get("_data_quality", {})
    completeness = quality.get("completeness_percent", 0)
    populated = quality.get("populated_fields", 0)
    total = quality.get("total_fields", 9)
    
    if completeness >= 70:
        indicator = "✓ HIGH"
        status = f"{populated}/{total} fields"
    elif completeness >= 40:
        indicator = "◐ MEDIUM"
        status = f"{populated}/{total} fields"
    else:
        indicator = "✗ LOW"
        status = f"{populated}/{total} fields"
    
    return f"Data Quality: {indicator} ({status}, {completeness}%)"


def format_investor(investor: dict) -> str:
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────
    firm = investor.get("firm") or "Unknown Firm"
    lines.append(f"\n  {firm.upper()}")
    lines.append(f"  {_SEP_LIGHT}")

    # Website
    website = investor.get("website", "")
    if website:
        lines.append(f"  Website  :  {website}")

    # Source URL (if different from website)
    source = investor.get("source_url", "")
    if source and source != website:
        lines.append(f"  Source   :  {source}")

    # Confidence bar
    score = investor.get("confidence_score", 0)
    lines.append(f"  Score    :  {_confidence_bar(score)}")
    
    # Data Quality Indicator
    quality_indicator = _data_quality_indicator(investor)
    lines.append(f"  {quality_indicator}")

    # ── Thesis ──────────────────────────────────────────────────────────
    thesis = investor.get("thesis", "").strip()
    if thesis:
        lines.append(_section_header("THESIS"))
        words = thesis.split()
        current = "    "
        for word in words:
            if len(current) + len(word) + 1 > 74:
                lines.append(current)
                current = f"    {word}"
            else:
                current += ("" if current == "    " else " ") + word
        if current.strip():
            lines.append(current)

    # ── Check Size ──────────────────────────────────────────────────────
    check_size = investor.get("check_size", "").strip()
    if check_size:
        lines.append(f"\n  Check Size  :  {check_size}")

    # ── Fund Info ───────────────────────────────────────────────────────
    fund_num = investor.get("fund_number", "").strip()
    fund_size = investor.get("fund_size", "").strip()
    if fund_num or fund_size:
        f_info = []
        if fund_num: f_info.append(fund_num)
        if fund_size: f_info.append(f"Size: {fund_size}")
        lines.append(f"  Fund Info   :  {', '.join(f_info)}")

    status = investor.get("active_status", "").strip()
    if status:
        lines.append(f"  Status      :  {status.title()}")

    # ── Investment Stage ────────────────────────────────────────────────
    stages = investor.get("investment_stage", [])
    if stages:
        lines.append(f"\n  Stage  :  {', '.join(stages)}")

    # ── Focus Sectors ───────────────────────────────────────────────────
    sectors = investor.get("focus_sectors", [])
    if sectors:
        lines.append(_section_header("FOCUS SECTORS"))
        for s in sectors:
            lines.append(_bullet(s))
    else:
        lines.append(_section_header("FOCUS SECTORS"))
        lines.append("    (Not specified)")

    # ── Domain Specializations ──────────────────────────────────────────
    specs = investor.get("domain_specializations", [])
    if specs:
        lines.append(_section_header("DOMAIN SPECIALIZATIONS"))
        for s in specs:
            lines.append(_bullet(s))
    else:
        lines.append(_section_header("DOMAIN SPECIALIZATIONS"))
        lines.append("    (Not specified)")

    # ── Geography ───────────────────────────────────────────────────────
    geo = investor.get("geography", [])
    if geo:
        lines.append(f"\n  Geography  :  {', '.join(geo)}")

    # ── Partners ────────────────────────────────────────────────────────
    partners = investor.get("partners", [])
    if partners:
        lines.append(_section_header("PARTNERS"))
        for p in partners[:MAX_PARTNERS_DISPLAY]:
            if isinstance(p, dict):
                name = p.get("name", "").strip()
                role = p.get("role", "").strip()
                if name:
                    entry = name + (f"  --  {role}" if role else "")
                    lines.append(_bullet(entry))
        if len(partners) > MAX_PARTNERS_DISPLAY:
            lines.append(f"    ... and {len(partners) - MAX_PARTNERS_DISPLAY} more")
    else:
        lines.append(_section_header("PARTNERS"))
        lines.append("    (No partners listed)")

    # ── Portfolio Companies ─────────────────────────────────────────────
    portfolio = investor.get("portfolio_companies", [])
    if portfolio:
        display = portfolio[:MAX_PORTFOLIO_DISPLAY]
        lines.append(_section_header(f"PORTFOLIO  ({len(portfolio)} companies)"))
        lines.append(f"    {',  '.join(display)}")
        if len(portfolio) > MAX_PORTFOLIO_DISPLAY:
            lines.append(f"    ... and {len(portfolio) - MAX_PORTFOLIO_DISPLAY} more")
    else:
        lines.append(_section_header("PORTFOLIO"))
        lines.append("    (No portfolio companies listed)")

    # ── Contact Links ───────────────────────────────────────────────────
    links = investor.get("contact_links", [])
    valid_links = []
    for link in links:
        if isinstance(link, dict):
            value = link.get("value", "").strip()
            if value:
                valid_links.append((link.get("type", "url"), value))
        elif isinstance(link, str) and link.strip():
            valid_links.append(("url", link.strip()))

    if valid_links:
        lines.append(_section_header("CONTACT"))
        for ltype, lval in valid_links:
            lines.append(_bullet(f"[{ltype}]  {lval}"))
    else:
        lines.append(_section_header("CONTACT"))
        lines.append("    (No contact information found)")

    process = investor.get("pitch_process", "").strip()
    if process:
        lines.append(f"\n  Pitch Process : {process}")

    lines.append(f"\n  {_SEP_LIGHT}")
    return "\n".join(_safe(l) for l in lines)