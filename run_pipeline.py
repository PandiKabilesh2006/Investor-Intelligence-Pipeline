import warnings
import json

warnings.filterwarnings("ignore")

from app.search.tavily_search import search_investors
from app.extraction.firecrawl_extract import extract_website
from app.parsing.gpt_parser import parse_investor

query = "AI seed investors"

search_results = search_investors(query)

first_result = search_results["results"][0]

url = first_result["url"]

print(f"\nSearching URL: {url}\n")

website_data = extract_website(url)

markdown_content = website_data.markdown

parsed_data = parse_investor(markdown_content)

print(json.dumps(parsed_data, indent=4))