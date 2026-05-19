import asyncio
import logging

from app.extraction.firecrawl_extract import extract_website


# =========================================
# CONCURRENCY LIMIT
# =========================================

MAX_CONCURRENT_EXTRACTIONS = 5


# =========================================
# SEMAPHORE
# =========================================

semaphore = asyncio.Semaphore(

    MAX_CONCURRENT_EXTRACTIONS
)


# =========================================
# SINGLE URL EXTRACTION
# =========================================

async def extract_single_url(url):

    async with semaphore:

        try:

            logging.info(

                f"Extracting URL: {url}"
            )


            # =========================================
            # RUN BLOCKING FIRECRAWL
            # =========================================

            result = await asyncio.to_thread(

                extract_website,

                url
            )


            return {

                "url": url,

                "markdown": result.markdown,

                "success": True
            }


        except Exception as error:

            logging.error(

                f"Extraction failed: "
                f"{url} | {error}"
            )


            return {

                "url": url,

                "markdown": "",

                "success": False
            }


# =========================================
# BULK EXTRACTION
# =========================================

async def extract_urls_async(urls):

    tasks = [

        extract_single_url(url)

        for url in urls
    ]


    results = await asyncio.gather(

        *tasks
    )


    return results