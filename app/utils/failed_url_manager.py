from datetime import datetime

from sqlalchemy import text

from app.database.db import SessionLocal
from app.config.extraction_policy import BLOCKED_URL_STATUS


# =========================================
# ADD FAILED URL
# =========================================

def add_failed_url(

    url,

    error_message,

    status="pending"
):

    session = SessionLocal()


    try:

        # =====================================
        # CHECK IF URL ALREADY EXISTS
        # =====================================

        existing = session.execute(

            text(

                """
                SELECT id, retry_count, status

                FROM failed_urls

                WHERE url = :url
                """
            ),

            {
                "url": url
            }
        ).fetchone()


        # =====================================
        # UPDATE EXISTING FAILED URL
        # =====================================

        if existing:

            failed_id = existing[0]

            retry_count = existing[1] + 1

            existing_status = existing[2]

            next_status = (
                BLOCKED_URL_STATUS
                if existing_status == BLOCKED_URL_STATUS or status == BLOCKED_URL_STATUS
                else status
            )


            session.execute(

                text(

                    """
                    UPDATE failed_urls

                    SET

                        error_message = :error_message,

                        retry_count = :retry_count,

                        last_attempt = :last_attempt,

                        status = :status

                    WHERE id = :failed_id
                    """
                ),

                {

                    "error_message": str(error_message),

                    "retry_count": retry_count,

                    "last_attempt": datetime.utcnow(),

                    "status": next_status,

                    "failed_id": failed_id
                }
            )


        # =====================================
        # INSERT NEW FAILED URL
        # =====================================

        else:

            session.execute(

                text(

                    """
                    INSERT INTO failed_urls (

                        url,

                        error_message,

                        retry_count,

                        last_attempt,

                        status

                    )

                    VALUES (

                        :url,

                        :error_message,

                        :retry_count,

                        :last_attempt,

                        :status
                    )
                    """
                ),

                {

                    "url": url,

                    "error_message": str(error_message),

                    "retry_count": 1,

                    "last_attempt": datetime.utcnow(),

                    "status": status
                }
            )


        session.commit()


        print(

            f"Failed URL stored: {url}"
        )


    except Exception as db_error:

        print(

            f"Failed storing failed URL: "
            f"{db_error}"
        )


        session.rollback()


    finally:

        session.close()


# =========================================
# GET FAILED URLS FOR RETRY
# =========================================

def get_failed_urls(

    max_retries=3,

    limit=100
):

    session = SessionLocal()


    try:

        results = session.execute(

            text(

                """
                SELECT

                    id,

                    url,

                    retry_count

                FROM failed_urls

                WHERE

                    retry_count <= :max_retries

                    AND

                    status = 'pending'

                ORDER BY last_attempt ASC

                LIMIT :limit
                """
            ),

            {

                "max_retries": max_retries,

                "limit": limit
            }
        ).fetchall()


        failed_urls = []


        for row in results:

            failed_urls.append({

                "id": row.id,

                "url": row.url,

                "retry_count": row.retry_count
            })


        return failed_urls


    finally:

        session.close()


# =========================================
# MARK FAILED URL AS RESOLVED
# =========================================

def mark_failed_url_resolved(

    failed_id
):

    session = SessionLocal()


    try:

        session.execute(

            text(

                """
                UPDATE failed_urls

                SET status = 'resolved'

                WHERE id = :failed_id
                """
            ),

            {

                "failed_id": failed_id
            }
        )


        session.commit()


    except Exception as db_error:

        print(

            f"Failed updating failed URL: "
            f"{db_error}"
        )

        session.rollback()


    finally:

        session.close()


def mark_url_blocked(url, error_message):
    add_failed_url(
        url=url,
        error_message=error_message,
        status=BLOCKED_URL_STATUS,
    )
