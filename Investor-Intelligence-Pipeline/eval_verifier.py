import sys
import time
from typing import List, Tuple

from app.verification.verifier import classify_website

# ---------------------------------------------------------
# The "Golden Dataset"
# ---------------------------------------------------------

# URLs that MUST be classified as "vc_firm"
KNOWN_VCS = [
    "https://radical.vc",          # The minimalist modern site
    "https://www.a16z.com",        # The massive firm
    "https://www.sequoiacap.com",  # Standard VC
    "https://blume.vc",            # Indian VC
    "https://www.accel.com",       # Global VC
    "https://av.vc",               # Short domain
    "https://www.ycombinator.com", # Accelerator/VC
]

# URLs that MUST be classified as something ELSE (blog, directory, unknown, etc)
KNOWN_JUNK = [
    "https://techcrunch.com",            # Media / Blog
    "https://www.crunchbase.com",        # Directory
    "https://openvc.app",                # Directory
    "https://www.stripe.com",            # Startup / SaaS
    "https://medium.com/@some_vc_guy",   # Blog platform
    "https://forbes.com/some-article",   # Media
]

def run_eval() -> None:
    print("=" * 50)
    print(" VERIFIER EVALUATION RUN")
    print("=" * 50)

    vc_passed = 0
    vc_failed = []

    print("\n[Testing Known VCs]")
    for url in KNOWN_VCS:
        print(f"  Fetching {url} ...", end=" ", flush=True)
        t0 = time.time()
        result = classify_website(url)
        t1 = time.time()
        
        if result == "vc_firm":
            print(f"[PASS] vc_firm ({t1-t0:.1f}s)")
            vc_passed += 1
        else:
            print(f"[FAIL] Expected vc_firm, got '{result}'")
            vc_failed.append((url, result))

    junk_passed = 0
    junk_failed = []

    print("\n[Testing Known Junk/Media]")
    for url in KNOWN_JUNK:
        print(f"  Fetching {url} ...", end=" ", flush=True)
        t0 = time.time()
        result = classify_website(url)
        t1 = time.time()
        
        if result != "vc_firm":
            print(f"[PASS] Blocked successfully as '{result}' ({t1-t0:.1f}s)")
            junk_passed += 1
        else:
            print(f"[FAIL] Expected block, got 'vc_firm'")
            junk_failed.append((url, result))

    # Summary
    print("\n" + "=" * 50)
    print(" EVALUATION SUMMARY")
    print("=" * 50)
    print(f"True Positives (Real VCs kept):     {vc_passed} / {len(KNOWN_VCS)}")
    print(f"True Negatives (Junk VCs blocked):  {junk_passed} / {len(KNOWN_JUNK)}")
    
    if vc_failed:
        print("\n[!] False Negatives (VCs that were incorrectly skipped):")
        for u, r in vc_failed:
            print(f"    - {u} (classified as {r})")
            
    if junk_failed:
        print("\n[!] False Positives (Junk that leaked through):")
        for u, r in junk_failed:
            print(f"    - {u} (classified as {r})")
            
    if not vc_failed and not junk_failed:
        print("\n🚀 PERFECT SCORE!")

if __name__ == "__main__":
    run_eval()
