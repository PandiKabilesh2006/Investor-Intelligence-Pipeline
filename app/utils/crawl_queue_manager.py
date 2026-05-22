from datetime import datetime

from sqlalchemy import text

from app.database.db import SessionLocal


# =========================================
# ADD URL TO CRAWL QUEUE
# =========================================

def add_to_crawl_queue(

    url,

    priority_score=1.0
):

    session = SessionLocal()


    try:

        existing = session.execute(

            text(

                """
                SELECT id

                FROM crawl_queue

                WHERE url = :url
                """
            ),

            {
                "url": url
            }
        ).fetchone()


        if existing:

            return


        session.execute(

            text(

                """
                INSERT INTO crawl_queue (

                    url,

                    priority_score,

                    discovered_at,

                    status

                )

                VALUES (

                    :url,

                    :priority_score,

                    :discovered_at,

                    :status
                )
                """
            ),

            {

                "url": url,

                "priority_score": priority_score,

                "discovered_at": datetime.utcnow(),

                "status": "pending"
            }
        )


        session.commit()


    finally:

        session.close()


# =========================================
# GET NEXT URLS TO CRAWL
# =========================================

def get_next_urls(

    limit=500
):

    session = SessionLocal()


    try:

        results = session.execute(

            text(

                """
                SELECT

                    id,

                    url

                FROM crawl_queue

                WHERE status = 'pending'

                ORDER BY priority_score DESC,

                discovered_at ASC

                LIMIT :limit
                """
            ),

            {
                "limit": limit
            }
        ).fetchall()


        return results


    finally:

        session.close()


# =========================================
# MARK URL AS CRAWLED
# =========================================

def mark_url_completed(

    queue_id
):

    session = SessionLocal()


    try:

        session.execute(

            text(

                """
                UPDATE crawl_queue

                SET

                    status = 'completed',

                    last_crawled = :last_crawled

                WHERE id = :queue_id
                """
            ),

            {

                "last_crawled": datetime.utcnow(),
                "queue_id": queue_id
            }
        )

        session.commit()

    finally:

        session.close()