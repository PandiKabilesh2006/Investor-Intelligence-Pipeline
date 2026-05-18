import warnings
import json

warnings.filterwarnings("ignore")

from app.extraction.firecrawl_extract import extract_website
from app.parsing.gpt_parser import parse_investor

url = "https://www.accel.com/team"

website_data = extract_website(url)

markdown_content = website_data.markdown

result = parse_investor(markdown_content)

print(json.dumps(result, indent=4))