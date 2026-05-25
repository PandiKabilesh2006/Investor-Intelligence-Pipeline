import asyncio
import logging

from app.extraction.firecrawl_extract import (
    extract_website
)

from app.config.settings import (
    EXTRACTION_MAX_CONCURRENT
)


# =========================================
# CONCURRENCY LIMIT
# =========================================

MAX_CONCURRENT_EXTRACTIONS = EXTRACTION_MAX_CONCURRENT


# =========================================
# SINGLE URL EXTRACTION
# =========================================

async def extract_single_url(

    url,

    semaphore
):

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

            markdown = result or ""

            return {

                "url": url,

                "markdown": markdown,

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

    # =========================================
    # CREATE LOOP-SAFE SEMAPHORE
    # =========================================

    semaphore = asyncio.Semaphore(

        MAX_CONCURRENT_EXTRACTIONS
    )


    tasks = [

        extract_single_url(

            url,

            semaphore
        )

        for url in urls
    ]


    results = await asyncio.gather(

        *tasks,

        return_exceptions=False
    )


    return results
