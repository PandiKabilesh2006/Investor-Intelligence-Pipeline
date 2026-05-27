import os
import sys

# Add project path to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.relevance.relevance_classifier import classify_investor_relevance
from app.parsing.gpt_parser import parse_investor

# Sample test data
query = "artificial intelligence series b investors"
title = "Outset Capital - Early Stage AI Venture Fund"
url = "https://outset.ai/"
snippet = "Outset Capital is a venture capital firm that invests in early-stage artificial intelligence and SaaS companies. We typically invest at Pre-Seed, Seed, and Series A/B stages."

sample_markdown = """
# Outset Capital
We invest in the absolute best founders at the earliest stages.

## Focus Areas
- Artificial Intelligence
- B2B SaaS
- AI Infrastructure

## Stages
- Pre-Seed
- Seed
- Series A

## Team
- Ali Rohde (General Partner)
- Kanjun Qiu (General Partner)
"""

print("==================================================")
print("TEST 1: TESTING WITH ACTIVE GROQ KEY (PRIMARY)")
print("==================================================")
try:
    print("\n--- Testing Relevance Classifier (Groq) ---")
    classification = classify_investor_relevance(query, title, url, snippet)
    print("Classification Output:")
    print(classification)

    print("\n--- Testing Parser (Groq) ---")
    parsed = parse_investor(sample_markdown)
    print("Parser Output:")
    print(parsed)
except Exception as e:
    print(f"Error in Test 1: {e}")

print("\n==================================================")
print("TEST 2: TESTING GROQ FAILURE / OLLAMA FALLBACK")
print("==================================================")
# Mock Groq API Key to be invalid to force fallback
os.environ["GROQ_API_KEY"] = "invalid_key_for_testing_purposes"

# Re-import or reinitialize clients if needed, but since we modify environ, 
# Groq client will throw an authentication/API error, triggering our try/except fallback.
# Let's reinitialize the Groq client in the modules to use the invalid key.
import app.relevance.relevance_classifier as rc
from groq import Groq
rc.client = Groq(api_key="invalid_key_for_testing_purposes")

import app.parsing.gpt_parser as gp
gp.groq_client = Groq(api_key="invalid_key_for_testing_purposes")

try:
    print("\n--- Testing Relevance Classifier Fallback (Ollama) ---")
    classification_fallback = classify_investor_relevance(query, title, url, snippet)
    print("Classification Output:")
    print(classification_fallback)

    print("\n--- Testing Parser Fallback (Ollama) ---")
    parsed_fallback = parse_investor(sample_markdown)
    print("Parser Output:")
    print(parsed_fallback)
except Exception as e:
    print(f"Error in Test 2: {e}")
