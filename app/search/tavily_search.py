import requests

from app.config.settings import TAVILY_API_KEY
from app.config.taxonomy import SEARCH_EXCLUDED_DOMAINS


TAVILY_URL = "https://api.tavily.com/search"


def search_investors(

    query,

    max_pages=5
):

    all_results = []

    seen_urls = set()


    for page in range(1, max_pages + 1):

        payload = {

            "api_key": TAVILY_API_KEY,

            "query": query,

            "search_depth": "advanced",

            "max_results": 10,

            "include_answer": False,

            "include_raw_content": False,

            "include_domains": [],

            "exclude_domains": SEARCH_EXCLUDED_DOMAINS,

            "page": page
        }


        try:

            response = requests.post(

                TAVILY_URL,

                json=payload,

                timeout=30
            )


            data = response.json()


            results = data.get("results", [])


            # =========================================
            # STOP PAGINATION
            # =========================================

            if not results:

                break


            new_results_found = False


            for result in results:

                url = result.get("url")


                if not url:

                    continue


                if url in seen_urls:

                    continue


                seen_urls.add(url)

                all_results.append(result)

                new_results_found = True


            # =========================================
            # STOP IF NO NEW URLS
            # =========================================

            if not new_results_found:

                break


        except Exception as error:

            print(

                f"Tavily search failed: "
                f"{error}"
            )


            break


    return {

        "results": all_results
    }
