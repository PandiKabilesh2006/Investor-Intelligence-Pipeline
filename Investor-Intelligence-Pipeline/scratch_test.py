import sys
import os
import tempfile
import csv
import json
from urllib.parse import urlparse

# Ensure local imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import app.verification.verifier as verifier
from app.verification.verifier import (
    _calculate_weighted_score,
    classify_website,
    VC_WEIGHTS,
    DIRECTORY_WEIGHTS,
    BLOG_WEIGHTS,
    STARTUP_WEIGHTS
)
from app.enrichment.email_guesser import generate_guessed_emails
from app.output.exporter import export_to_csv
from app.parsing.schema import InvestorSchema
from run_pipeline import get_category_slug

def run_tests():
    print("=" * 60)
    print("      PIPELINE EDGE-CASE ADVANCED DIAGNOSTIC RUN")
    print("=" * 60)

    failures = 0

    # ----------------------------------------------------
    # EDGE CASE 1: Domain Left-Stripping Gotcha Check
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 1: Left-Side 'www.' Stripping")
    print("-" * 50)
    
    test_domains = [
        ("www.williams.vc", "williams.vc"),
        ("williams.vc", "williams.vc"),
        ("www.wunderbar.com", "wunderbar.com"),
        ("wunderbar.com", "wunderbar.com"),
        ("www.worldvc.com", "worldvc.com"),
        ("worldvc.com", "worldvc.com"),
        ("www.www.com", "www.com")
    ]
    
    for input_url, expected in test_domains:
        domain = input_url.lower()
        if domain.startswith("www."):
            domain = domain[4:]
            
        status = "✓ PASS" if domain == expected else "✗ FAIL"
        if domain != expected:
            failures += 1
        print(f"  Input: {input_url:<20} -> Result: {domain:<15} [{status}]")
        
    # ----------------------------------------------------
    # EDGE CASE 2: Category Slug Cleaning Check
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 2: CRM Category Slug Sanitization")
    print("-" * 50)
    
    test_presets = [
        ("1", "ai_machine_learning"),
        ("2", "enterprise_saas"),
        ("3", "developer_tools_infrastructure"),
        ("4", "voice_ai_conversational_ai"),
        ("5", "fintech_financial_services"),
        ("6", "healthcare_biotech"),
        ("7", "india_south_asia"),
        ("8", "custom")
    ]
    
    for choice, expected in test_presets:
        slug = get_category_slug(choice)
        status = "✓ PASS" if slug == expected else "✗ FAIL"
        if slug != expected:
            failures += 1
        print(f"  Choice: {choice} -> Slug: {slug:<30} [{status}]")

    # ----------------------------------------------------
    # EDGE CASE 3: Points-Based Regex Classification Check
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 3: Points-Based Regex Classification")
    print("-" * 50)
    
    test_pages = [
        ("We are a venture capital firm with a clear investment thesis focused on early-stage seed investing.", "vc_firm"),
        ("Our portfolio companies and our investments include deep tech, enterprise software, and series a startups.", "vc_firm"),
        ("Book demo and sign up for free now. Flexible pricing plans start at $15/month.", "startup"),
        ("Published on our Medium blog. Read more here about our comments section.", "blog")
    ]
    
    for content, expected_type in test_pages:
        text = content.lower()
        vc_score = _calculate_weighted_score(text, VC_WEIGHTS)
        directory_score = _calculate_weighted_score(text, DIRECTORY_WEIGHTS)
        blog_score = _calculate_weighted_score(text, BLOG_WEIGHTS)
        startup_score = _calculate_weighted_score(text, STARTUP_WEIGHTS)

        scores = {
            "vc_firm": vc_score,
            "directory": directory_score,
            "blog": blog_score,
            "startup": startup_score,
        }

        best = max(scores, key=scores.get)
        best_score = scores[best]

        if best_score < 5:
            res = "unknown"
        elif directory_score >= vc_score and directory_score >= 5:
            res = "directory"
        elif startup_score >= vc_score and startup_score >= 5:
            res = "startup"
        elif blog_score >= vc_score and blog_score >= 5:
            res = "blog"
        else:
            res = best

        status = "✓ PASS" if res == expected_type else "✗ FAIL"
        if res != expected_type:
            failures += 1
        print(f"  Content snippet: \"{content[:45]}...\"")
        print(f"  Scores: VC={vc_score} Dir={directory_score} Blog={blog_score} Startup={startup_score}")
        print(f"  Expected: {expected_type:<10} -> Result: {res:<10} [{status}]")
        print("  " + "-" * 50)

    # ----------------------------------------------------
    # EDGE CASE 4: Email Guesser Edge Cases
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 4: Email Guesser Robustness & Variation Checks")
    print("-" * 50)
    
    test_investor_data = [
        {
            "website": "https://www.williams.vc",
            "partners": [
                {"name": "Marc Andreessen"},
                {"name": "J. P. Morgan"},
                {"name": "Alice"},
                {"name": ""},
                {"name": "Mr. John  Smith"}
            ]
        },
        {
            "website": "williams.vc",  # No protocol
            "partners": [
                {"name": "Bob Vance"}
            ]
        },
        {
            "website": "",  # Empty website
            "partners": [
                {"name": "No Email Partner"}
            ]
        },
        {
            "website": "https://a16z.com",
            "partners": None  # Malformed partners (None instead of list)
        }
    ]
    
    # Run email guesser (mutates list in-place)
    generate_guessed_emails(test_investor_data)
    
    # Subtest 1: Williams VC partner list
    williams_guesses = test_investor_data[0].get("guessed_emails", [])
    expected_williams = [
        "Marc Andreessen: [marc@williams.vc, marc.andreessen@williams.vc, mandreessen@williams.vc]",
        "J. P. Morgan: [j@williams.vc, j.morgan@williams.vc, jmorgan@williams.vc]",
        "Alice: [alice@williams.vc]",
        "Mr. John  Smith: [mr@williams.vc, mr.smith@williams.vc, msmith@williams.vc]"
    ]
    
    for exp in expected_williams:
        status = "✓ PASS" if exp in williams_guesses else "✗ FAIL"
        if exp not in williams_guesses:
            failures += 1
        print(f"  Expected guess: {exp}")
        print(f"  Actual status:                [{status}]")
        print("  " + "-" * 50)
        
    # Subtest 2: Website without protocol domain parsing check
    williams_no_proto_guesses = test_investor_data[1].get("guessed_emails", [])
    exp_no_proto = "Bob Vance: [bob@williams.vc, bob.vance@williams.vc, bvance@williams.vc]"
    status = "✓ PASS" if exp_no_proto in williams_no_proto_guesses else "✗ FAIL"
    if exp_no_proto not in williams_no_proto_guesses:
        failures += 1
    print(f"  No-protocol parsing target: {exp_no_proto}")
    print(f"  Actual status:                [{status}]")
    print("  " + "-" * 50)

    # Subtest 3: Empty website check
    empty_web_guesses = test_investor_data[2].get("guessed_emails", [])
    status = "✓ PASS" if empty_web_guesses == [] else "✗ FAIL"
    if empty_web_guesses != []:
        failures += 1
    print(f"  Empty website results: {empty_web_guesses} (Expected: [])")
    print(f"  Actual status:                [{status}]")
    print("  " + "-" * 50)

    # Subtest 4: Malformed partners check
    malformed_guesses = test_investor_data[3].get("guessed_emails", [])
    status = "✓ PASS" if malformed_guesses == [] else "✗ FAIL"
    if malformed_guesses != []:
        failures += 1
    print(f"  Malformed partners list: {malformed_guesses} (Expected: [])")
    print(f"  Actual status:                [{status}]")
    print("  " + "-" * 50)

    # ----------------------------------------------------
    # EDGE CASE 5: Cloudflare Bypass Fallback Verification
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 5: Cloudflare Bypass Fallback Verification")
    print("-" * 50)
    
    # Back up original verifier globals
    original_extract_page_text = verifier._extract_page_text
    original_domain_cache = verifier._domain_cache.copy()
    original_save_domain_cache = verifier._save_domain_cache
    
    try:
        # Set up mock behaviors: empty response representing Cloudflare blocking
        verifier._extract_page_text = lambda url: ""
        verifier._domain_cache.clear()
        verifier._save_domain_cache = lambda: None
        
        # Williams Ventures has a strong indicator ("ventures")
        res_indicator = classify_website("https://williamsventures.com")
        status_ind = "✓ PASS" if res_indicator == "vc_firm" else "✗ FAIL"
        if res_indicator != "vc_firm":
            failures += 1
        print(f"  Target: https://williamsventures.com (blocked page, 'ventures' indicator)")
        print(f"  Expected: vc_firm  -> Result: {res_indicator:<10} [{status_ind}]")
        print("  " + "-" * 50)
        
        # Williams Design has no strong indicator
        res_non_indicator = classify_website("https://williamsdesign.com")
        status_non = "✓ PASS" if res_non_indicator == "unknown" else "✗ FAIL"
        if res_non_indicator != "unknown":
            failures += 1
        print(f"  Target: https://williamsdesign.com (blocked page, no VC indicator)")
        print(f"  Expected: unknown  -> Result: {res_non_indicator:<10} [{status_non}]")
        print("  " + "-" * 50)

    finally:
        # Restore original verifier globals
        verifier._extract_page_text = original_extract_page_text
        verifier._domain_cache = original_domain_cache
        verifier._save_domain_cache = original_save_domain_cache

    # ----------------------------------------------------
    # EDGE CASE 6: Verifier Caching Load/Save Persistence
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 6: Verifier Caching Load/Save Persistence")
    print("-" * 50)
    
    # Back up original verifier globals
    original_extract_page_text = verifier._extract_page_text
    original_domain_cache = verifier._domain_cache.copy()
    original_save_domain_cache = verifier._save_domain_cache
    
    try:
        # Clear cache and mock save
        verifier._domain_cache.clear()
        verifier._save_domain_cache = lambda: None
        
        # Seed cache manually
        verifier._domain_cache["testvc.com"] = "vc_firm"
        
        # Mock extract to raise an error if called (proves cache hit avoids network fetch)
        def crash_on_call(url):
            raise AssertionError("Network extractor called despite cache hit!")
        
        verifier._extract_page_text = crash_on_call
        
        # Call classifier on seeded domain
        res_cached = classify_website("https://testvc.com")
        status_cache = "✓ PASS" if res_cached == "vc_firm" else "✗ FAIL"
        if res_cached != "vc_firm":
            failures += 1
        print(f"  Target: https://testvc.com (domain pre-cached as vc_firm)")
        print(f"  Expected: vc_firm  -> Result: {res_cached:<10} [{status_cache}]")
        print("  " + "-" * 50)
        
        # Verify cache gets populated on a new successful classification
        verifier._domain_cache.clear()
        # Mock extractor to return startup text
        verifier._extract_page_text = lambda url: "Book demo and sign up for free now. Flexible pricing plans start at $15/month. We offer a wonderful product for everyone in the world."
        
        res_new = classify_website("https://newstartup.com")
        in_cache = verifier._domain_cache.get("newstartup.com")
        
        status_cache_update = "✓ PASS" if in_cache == "startup" else "✗ FAIL"
        if in_cache != "startup":
            failures += 1
        print(f"  Target: https://newstartup.com (uncached, should classify and cache)")
        print(f"  Expected cache entry: startup -> Actual: {in_cache:<10} [{status_cache_update}]")
        print("  " + "-" * 50)

    finally:
        # Restore original verifier globals
        verifier._extract_page_text = original_extract_page_text
        verifier._domain_cache = original_domain_cache
        verifier._save_domain_cache = original_save_domain_cache

    # ----------------------------------------------------
    # EDGE CASE 7: CSV Flat String Conversions
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 7: CSV Flat String Conversions")
    print("-" * 50)
    
    test_csv_investors = [
        {
            "firm": "Williams VC",
            "website": "https://www.williams.vc",
            "confidence_score": 19,
            "partners": [
                {"name": "Marc Andreessen", "role": "General Partner"},
                {"name": "Ben Horowitz", "role": "General Partner"}
            ],
            "portfolio_companies": ["Github", "Slack", "Skype"],
            "contact_links": [
                {"type": "twitter", "value": "https://twitter.com/williamsvc"},
                {"type": "linkedin", "value": "https://linkedin.com/company/williamsvc"}
            ],
            "guessed_emails": ["marc@williams.vc", "ben@williams.vc"]
        }
    ]
    
    # Write to a temporary CSV file
    temp_dir = tempfile.gettempdir()
    temp_csv_path = os.path.join(temp_dir, "test_investors_export.csv")
    
    try:
        export_to_csv(test_csv_investors, temp_csv_path)
        
        # Read back and verify values
        with open(temp_csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        if not rows:
            failures += 1
            print("  ✗ FAIL: CSV contains no rows!")
        else:
            row = rows[0]
            
            # Subtest 1: Check partners flattening
            expected_partners = "Marc Andreessen (General Partner) | Ben Horowitz (General Partner)"
            status_partners = "✓ PASS" if row.get("partners") == expected_partners else "✗ FAIL"
            if row.get("partners") != expected_partners:
                failures += 1
            print(f"  Field 'partners': {row.get('partners')}")
            print(f"  Expected:       {expected_partners}")
            print(f"  Status:         [{status_partners}]")
            print("  " + "-" * 50)
            
            # Subtest 2: Check portfolio companies list joining
            expected_portfolio = "Github, Slack, Skype"
            status_portfolio = "✓ PASS" if row.get("portfolio_companies") == expected_portfolio else "✗ FAIL"
            if row.get("portfolio_companies") != expected_portfolio:
                failures += 1
            print(f"  Field 'portfolio_companies': {row.get('portfolio_companies')}")
            print(f"  Expected:                    {expected_portfolio}")
            print(f"  Status:                      [{status_portfolio}]")
            print("  " + "-" * 50)
            
            # Subtest 3: Check contact links flattening
            expected_contacts = "twitter: https://twitter.com/williamsvc | linkedin: https://linkedin.com/company/williamsvc"
            status_contacts = "✓ PASS" if row.get("contact_links") == expected_contacts else "✗ FAIL"
            if row.get("contact_links") != expected_contacts:
                failures += 1
            print(f"  Field 'contact_links': {row.get('contact_links')}")
            print(f"  Expected:              {expected_contacts}")
            print(f"  Status:                [{status_contacts}]")
            print("  " + "-" * 50)
            
            # Subtest 4: Check guessed emails list joining
            expected_emails = "marc@williams.vc, ben@williams.vc"
            status_emails = "✓ PASS" if row.get("guessed_emails") == expected_emails else "✗ FAIL"
            if row.get("guessed_emails") != expected_emails:
                failures += 1
            print(f"  Field 'guessed_emails': {row.get('guessed_emails')}")
            print(f"  Expected:               {expected_emails}")
            print(f"  Status:                 [{status_emails}]")
            print("  " + "-" * 50)
            
    finally:
        # Clean up temporary CSV file
        if os.path.exists(temp_csv_path):
            try:
                os.remove(temp_csv_path)
            except:
                pass

    # ----------------------------------------------------
    # EDGE CASE 8: Pydantic Schema Coercion Checks (Kitven List Parsing Error Fix)
    # ----------------------------------------------------
    print("\n[+] Testing Edge Case 8: Pydantic Schema Coercion (Kitven Parsing Fix)")
    print("-" * 50)
    
    # Simulates the erroneous output returned by Groq/LLM for KITVEN where fund_number is returned as a list
    test_json_data = {
        "firm": ["Kitven"],
        "website": ["https://www.kitven.in"],
        "thesis": "Investing in Karnataka-based IT/Biotech startups.",
        "focus_sectors": "Biotechnology", # Single string instead of list
        "fund_number": ["KIT"], # LIST returned where string was expected (original crash reason)
        "fund_size": "₹200 Crore",
        "active_status": ["Actively Deploying"],
        "partners": ["Shri A. B. Patil"], # Flat string in list instead of Dict
        "portfolio_companies": [{"name": "Acellere"}, "Nymble Labs"], # Mixed dict/string
        "contact_links": ["info@kitven.com"] # Flat string instead of ContactLink dict
    }
    
    try:
        validated = InvestorSchema.model_validate(test_json_data)
        res_dict = validated.model_dump()
        
        # Check string list/dict coercions
        status_firm = "✓ PASS" if res_dict["firm"] == "Kitven" else "✗ FAIL"
        if res_dict["firm"] != "Kitven":
            failures += 1
            
        status_web = "✓ PASS" if res_dict["website"] == "https://www.kitven.in" else "✗ FAIL"
        if res_dict["website"] != "https://www.kitven.in":
            failures += 1
            
        status_fund = "✓ PASS" if res_dict["fund_number"] == "KIT" else "✗ FAIL"
        if res_dict["fund_number"] != "KIT":
            failures += 1
            
        status_sector = "✓ PASS" if res_dict["focus_sectors"] == ["Biotechnology"] else "✗ FAIL"
        if res_dict["focus_sectors"] != ["Biotechnology"]:
            failures += 1
            
        status_partners = "✓ PASS" if res_dict["partners"] == [{"name": "Shri A. B. Patil", "role": ""}] else "✗ FAIL"
        if res_dict["partners"] != [{"name": "Shri A. B. Patil", "role": ""}]:
            failures += 1
            
        status_portfolio = "✓ PASS" if res_dict["portfolio_companies"] == ["Acellere", "Nymble Labs"] else "✗ FAIL"
        if res_dict["portfolio_companies"] != ["Acellere", "Nymble Labs"]:
            failures += 1
            
        status_contacts = "✓ PASS" if res_dict["contact_links"] == [{"type": "url", "value": "info@kitven.com"}] else "✗ FAIL"
        if res_dict["contact_links"] != [{"type": "url", "value": "info@kitven.com"}]:
            failures += 1
            
        print(f"  Field 'firm':              {res_dict['firm']:<20} [{status_firm}]")
        print(f"  Field 'website':           {res_dict['website']:<20} [{status_web}]")
        print(f"  Field 'fund_number':       {res_dict['fund_number']:<20} [{status_fund}]")
        print(f"  Field 'focus_sectors':     {res_dict['focus_sectors']} [{status_sector}]")
        print(f"  Field 'partners':          {res_dict['partners']} [{status_partners}]")
        print(f"  Field 'portfolio_companies': {res_dict['portfolio_companies']} [{status_portfolio}]")
        print(f"  Field 'contact_links':     {res_dict['contact_links']} [{status_contacts}]")
        
    except Exception as e:
        failures += 1
        print(f"  ✗ FAIL: Pydantic parsing raised a validation error: {e}")

    print("\n" + "=" * 60)
    if failures == 0:
        print("    ★ ALL PIPELINE EDGE CASES PASSED SUCCESSFULLY ★")
    else:
        print(f"    ⚠️ DIAGNOSTIC DETECTED {failures} FAILING EDGE CASES")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
