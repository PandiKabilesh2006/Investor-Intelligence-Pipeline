import requests
from app.config.settings import TAVILY_API_KEY

def search_investors(query):

    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 5
    }

    response = requests.post(url, json=payload)

    return response.json()