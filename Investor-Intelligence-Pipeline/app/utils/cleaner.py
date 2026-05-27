"""
Content cleaner: filters raw Firecrawl markdown down to
investor-relevant paragraphs before sending to the LLM.
"""

import re

KEYWORDS = [
    "investment", "investor", "portfolio", "partner",
    "venture", "team", "seed", "series", "saas", "ai",
    "voice", "enterprise", "automation", "founder", "funding",
    "capital", "startup", "equity", "thesis", "backed",
    "machine learning", "artificial intelligence", "deep tech",
    "contact", "email", "linkedin", "managing partner",
    "general partner", "pre-seed", "growth", "check size",
    "fund", "vc", "angel",
]

# Regex patterns for detecting contact information
EMAIL_PATTERN = r'[\w\.-]+@[\w\.-]+\.\w{2,}'
PHONE_PATTERN = r'\+?1?\s?[\(\-\.]?\d{3}[\)\-\.]?\s?\d{3}[\-\.]?\d{4}'
LINKEDIN_PATTERN = r'linkedin\.com/(?:in|company)/[\w\-]+'

# Default char limits per backend
DEFAULT_MAX_CHARS_GROQ   = 6000    # Reduced from 12k to respect Groq free tier TPM limits
DEFAULT_MAX_CHARS_OLLAMA = 5000    # Small models lose accuracy beyond this


def clean_content(markdown: str, max_chars: int = DEFAULT_MAX_CHARS_OLLAMA) -> str:
    """
    Extract investor-relevant lines from raw markdown.
    Prioritizes lines containing contact information.

    Args:
        markdown:  Raw Firecrawl markdown string
        max_chars: Output character limit. Use DEFAULT_MAX_CHARS_GROQ for
                   Groq/70B models, DEFAULT_MAX_CHARS_OLLAMA for small models.

    Strategy:
    - Keep lines that contain at least one keyword
    - PRIORITY: Always include lines with contact information (emails, phones, LinkedIn)
    - Skip very short lines (< 15 chars) — nav fragments
    - Skip very long lines (> 400 words) — full-page dumps
    - Skip lines with excessive commas (> 20) — raw data tables
    - Skip long pipe lines (> 300 chars) — data dumps, but keep short ones (tables)
    - Deduplicate identical lines
    - Contact sections go first to maximize extraction
    """
    if not markdown:
        return ""

    lines = markdown.split("\n")
    contact_lines = []
    regular_lines = []
    seen: set[str] = set()

    for line in lines:
        line = line.strip()

        if len(line) < 15:
            continue

        word_count = len(line.split())
        if word_count > 400:
            continue

        if line.count(",") > 20:
            continue

        # Allow pipe lines only if they're short (table cells, not giant dumps)
        if "|" in line and len(line) > 300:
            continue

        if line in seen:
            continue
        
        seen.add(line)
        lower = line.lower()
        
        # Check if line contains contact information (priority)
        has_contact_info = (
            re.search(EMAIL_PATTERN, line) or
            re.search(PHONE_PATTERN, line) or
            re.search(LINKEDIN_PATTERN, line) or
            any(phrase in lower for phrase in ["email:", "phone:", "contact:", "reach out", "get in touch", "founding team", "team members", "our team"])
        )
        
        # Check for relevant keywords
        has_keywords = any(kw in lower for kw in KEYWORDS)
        
        if has_contact_info or has_keywords:
            if has_contact_info:
                contact_lines.append(line)
            else:
                regular_lines.append(line)

    # Combine: contact lines first (higher priority), then regular keyword lines
    relevant = contact_lines + regular_lines
    
    # Increase max_chars for better contact preservation
    effective_max = max_chars + 2000 if contact_lines else max_chars
    
    return "\n\n".join(relevant)[:effective_max]