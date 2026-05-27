import os
import sys

# Add project path to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.parsing.gpt_parser import normalize_output

# User's exact payload from Ollama fallback
malformed_payload = {
    "firm": "[{'name': 'Accel Partners', 'website': 'http://www.accel.com/', 'partners': [], 'focus_sectors': ['B2B SaaS'], 'investment_stage': ['Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Slack', 'Dropbox', 'Atlassian', 'DocuSign', 'Braintree'], 'geography': ['Global']}, {'name': 'Bessemer Venture Partners', 'website': 'http://www.bvp.com/', 'partners': [], 'focus_sectors': ['B2B SaaS'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Slack', 'Dropbox', 'Atlassian', 'DocuSign', 'Braintree'], 'geography': ['Global']}, {'name': 'Emergence Capital', 'website': 'http://www.emcap.com/', 'partners': [], 'focus_sectors': ['Enterprise'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Yammer', 'Veeva', 'Box'], 'geography': ['United States']}, {'name': 'Matrix Partners', 'website': 'http://www.matrixpartners.com/', 'partners': [], 'focus_sectors': ['B2B SaaS'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Carbon Black', 'HubSpot', 'Zendesk'], 'geography': ['Global']}, {'name': 'Point Nine Capital', 'website': 'http://www.pointninecap.com/', 'partners': [], 'focus_sectors': ['B2B SaaS', 'Online Marketplaces'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Zendesk', 'Geckoboard', 'ChartMogul'], 'geography': ['Berlin']}, {'name': 'SaaStr Fund', 'website': 'https://www.saastr.com/saastr-fund-looking-to-fund-2-4-great-saas-companies-in-2023/', 'partners': [], 'focus_sectors': ['B2B SaaS'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Algolia', 'Mixmax', 'Talkdesk'], 'geography': ['Global']}, {'name': 'Scale Venture Partners', 'website': 'http://www.scalevp.com/', 'partners': [], 'focus_sectors': ['B2B SaaS'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['HubSpot', 'Box', 'Exact Target'], 'geography': ['Global']}, {'name': 'In-Q-Tel', 'website': 'https://www.iqt.org/', 'partners': [], 'focus_sectors': ['Enterprise'], 'investment_stage': ['Seed', 'Series A', 'Series B', 'Growth Stage'], 'portfolio_companies': ['Palantir Technologies', 'Spotfire', 'MongoDB'], 'geography': ['Global']}]",
    "website": "",
    "partners": [],
    "focus_sectors": [],
    "investment_stage": [],
    "portfolio_companies": [],
    "geography": [],
    "contact_links": []
}

print("Running normalize_output on the malformed multi-firm payload...\n")
normalized = normalize_output(malformed_payload)

print("Normalized Result:")
import json
print(json.dumps(normalized, indent=4))

# Verification assertions
assert normalized["firm"] == "Accel Partners"
assert normalized["website"] == "http://www.accel.com/"
assert normalized["focus_sectors"] == ["B2B SaaS"]
assert "Slack" in normalized["portfolio_companies"]

print("\nSUCCESS! The first firm has been extracted perfectly and mapped to the top-level keys!")

# ==========================================================
# ADDITIONAL TESTS FOR BRACKETS / MALFORMED LIST ARTIFACTS
# ==========================================================
print("\n--- Running additional tests for list bracket/malformed firm strings ---")

# Test case 1: List of plain strings
payload_str_list = {"firm": "['Accel Partners', 'Bessemer Venture Partners']"}
res1 = normalize_output(payload_str_list)
print(f"List of strings input: {payload_str_list['firm']} -> Output: {res1['firm']}")
assert res1["firm"] == "Accel Partners"

# Test case 2: Malformed list representation string
payload_malformed = {"firm": "['a','ab','ac'a,ab'']"}
res2 = normalize_output(payload_malformed)
print(f"Malformed list input: {payload_malformed['firm']} -> Output: {res2['firm']}")
assert res2["firm"] == "a"

# Test case 3: Single element bracket string
payload_single = {"firm": "['a']"}
res3 = normalize_output(payload_single)
print(f"Single bracket input: {payload_single['firm']} -> Output: {res3['firm']}")
assert res3["firm"] == "a"

print("\nALL BRACKET AND MALFORMED FIRM NAME TESTS PASSED SUCCESSFULLY!")
