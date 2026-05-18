from app.extraction.firecrawl_extract import extract_website

import warnings

warnings.filterwarnings("ignore")
url = "https://www.accel.com"

result = extract_website(url)

print(result)