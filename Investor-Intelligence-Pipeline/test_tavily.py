import sys
from app.search.tavily_search import search_investors
try:
    domains = [f"junkdomain{i}.com" for i in range(500)]
    res = search_investors('enterprise AI venture capital fund portfolio', max_results=100, exclude_domains=domains)
    print(f"Success! Results: {len(res.get('results', []))}")
except Exception as e:
    print(f"Error: {e}")
