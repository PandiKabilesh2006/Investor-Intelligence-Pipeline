import requests
from urllib.parse import urlparse
import re

# ==========================================
# DOMAIN ANALYSIS & PRE-FILTERING
# ==========================================

# Keywords indicating legitimate VC/investment firm domains
VC_DOMAIN_KEYWORDS = [
    "venture", "capital", "fund", "investment", "invest",
    "private equity", "growth", "growth equity", "accelerator",
    "incubator", "partners", "group", "consulting"
]

# Domains to block - not VC firms
BLOCKED_DOMAINS = [
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "crunchbase.com", "pitchbook.com", "angellist.com", "producthunt.com",
    "github.com", "stackoverflow.com", "medium.com", "substack.com",
    "news.ycombinator.com", "reddit.com", "quora.com"
]

# URL patterns to skip - not full company websites
SKIP_PATTERNS = [
    r"/blog/", r"/news/", r"/article/", r"/post/",
    r"/author/", r"/search", r"/tag/", r"/category/",
    r"/press-release", r"/careers", r"/jobs", r"/apply",
    r"^https?://blog\.", r"^https?://news\.", r"^https?://press\."
]


def is_blocked_domain(url: str) -> bool:
    """Check if URL is from a blocked social/directory domain"""
    url_lower = url.lower()
    return any(domain in url_lower for domain in BLOCKED_DOMAINS)


def matches_skip_pattern(url: str) -> bool:
    """Check if URL matches patterns we want to skip"""
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in SKIP_PATTERNS)


def looks_like_vc_domain(url: str) -> bool:
    """
    Check if domain name suggests it's a VC firm.
    Returns True if domain contains VC-related keywords or passes heuristics.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        
        # Check for VC keywords in domain
        if any(keyword in domain for keyword in VC_DOMAIN_KEYWORDS):
            return True
        
        # If domain is very short and specific (e.g., "sequoia.com"), likely legitimate
        if len(domain.split('.')[0]) < 20:  # Not a very long subdomain
            return True
        
        return False
    except:
        return True  # If unsure, give benefit of doubt


def check_page_size(url: str, timeout: int = 5) -> bool:
    """
    Use HTTP HEAD request to check if page exists and has sufficient size.
    Returns True if page is likely to have content (>10KB).
    Returns False if unreachable or too small (likely landing page).
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        
        # Check status code
        if response.status_code >= 400:
            return False
        
        # Check Content-Length header if available
        content_length = response.headers.get('content-length')
        if content_length:
            try:
                size_bytes = int(content_length)
                if size_bytes < 10000:  # Less than 10KB
                    return False
            except:
                pass
        
        return True
    
    except requests.Timeout:
        # Timeout - assume site exists but slow, give benefit of doubt
        return True
    except requests.ConnectionError:
        return False
    except Exception as e:
        # On other errors, assume it's worth checking
        return True


def detect_redirect_spam(url: str, max_redirects: int = 2, timeout: int = 5) -> bool:
    """
    Detect if URL redirects to low-quality destinations.
    Returns True if URL is safe to process.
    Returns False if it redirects to spam/low-quality sites.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Use requests session to follow redirects
        session = requests.Session()
        response = session.head(url, timeout=timeout, allow_redirects=False, headers=headers)
        
        redirect_count = 0
        current_url = url
        
        while 300 <= response.status_code < 400 and redirect_count < max_redirects:
            location = response.headers.get('location')
            if not location:
                break
            
            # Check if redirect is to blocked domain
            if is_blocked_domain(location):
                return False
            
            # Follow redirect
            current_url = location if location.startswith('http') else url.split('//', 1)[0] + '//' + urlparse(url).netloc + location
            response = session.head(current_url, timeout=timeout, allow_redirects=False, headers=headers)
            redirect_count += 1
        
        return True
    
    except:
        return True  # If check fails, assume it's OK


def pre_filter_url(url: str, verbose: bool = False) -> tuple[bool, str]:
    """
    Pre-filter URL before expensive Firecrawl extraction.
    
    Args:
        url: URL to check
        verbose: Print filtering reasons if True
        
    Returns:
        (should_process, reason) tuple
        - should_process: True if URL should be extracted with Firecrawl
        - reason: String explaining the filtering decision
    """
    
    if not url:
        return False, "Empty URL"
    
    # Step 1: Block known non-VC domains
    if is_blocked_domain(url):
        reason = "Blocked domain (social media / directory)"
        if verbose:
            print(f"⏭️  {reason}: {url}")
        return False, reason
    
    # Step 2: Skip blog/news/article URLs
    if matches_skip_pattern(url):
        reason = "Matches skip pattern (blog/news/article/etc)"
        if verbose:
            print(f"⏭️  {reason}: {url}")
        return False, reason
    
    # Step 3: Check if domain name suggests VC firm
    if not looks_like_vc_domain(url):
        reason = "Domain name doesn't suggest VC firm"
        if verbose:
            print(f"⏭️  {reason}: {url}")
        return False, reason
    
    # Step 4: Check for redirect spam
    if not detect_redirect_spam(url):
        reason = "Redirects to blocked/low-quality site"
        if verbose:
            print(f"⏭️  {reason}: {url}")
        return False, reason
    
    # Step 5: Check page size (lightweight HEAD request)
    if not check_page_size(url):
        reason = "Page too small or unreachable (<10KB)"
        if verbose:
            print(f"⏭️  {reason}: {url}")
        return False, reason
    
    # Passed all filters
    if verbose:
        print(f"✅ URL passed pre-filter: {url}")
    return True, "Passed all checks"


def filter_urls_batch(urls: list, verbose: bool = False) -> dict:
    """
    Filter a batch of URLs before processing.
    
    Args:
        urls: List of URLs to filter
        verbose: Print detailed filtering info if True
        
    Returns:
        {
            'passed': [urls that passed],
            'filtered': {url: reason} of rejected URLs,
            'stats': {
                'total': int,
                'passed': int,
                'filtered': int,
                'reduction_percent': float
            }
        }
    """
    passed = []
    filtered = {}
    
    for url in urls:
        should_process, reason = pre_filter_url(url, verbose=verbose)
        if should_process:
            passed.append(url)
        else:
            filtered[url] = reason
    
    reduction_percent = (len(filtered) / len(urls) * 100) if urls else 0
    
    return {
        'passed': passed,
        'filtered': filtered,
        'stats': {
            'total': len(urls),
            'passed': len(passed),
            'filtered': len(filtered),
            'reduction_percent': round(reduction_percent, 1)
        }
    }
