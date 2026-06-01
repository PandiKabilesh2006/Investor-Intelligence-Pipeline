from urllib.parse import urlparse

from sqlalchemy import text

from app.database.db import SessionLocal
from app.database.models import ReviewQueue
from app.utils.failed_url_manager import mark_url_blocked


def _host(url):
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def sync_rejected_blocklist():
    session = SessionLocal()

    try:
        rejected_items = (
            session.query(ReviewQueue)
            .filter(ReviewQueue.status == "rejected")
            .all()
        )
        urls = set()
        hosts = set()

        for item in rejected_items:
            payload = item.extracted_payload or {}
            candidates = [
                item.url,
                payload.get("source_url") if isinstance(payload, dict) else "",
                payload.get("website") if isinstance(payload, dict) else "",
            ]

            for raw_url in candidates:
                raw_url = str(raw_url or "").strip()

                if not raw_url.startswith(("http://", "https://")):
                    continue

                hostname = _host(raw_url)

                if not hostname:
                    continue

                hosts.add(hostname)
                urls.add(raw_url)

        for url in urls:
            mark_url_blocked(
                url,
                "Previously rejected in review queue; permanently blocked from pipeline discovery.",
            )

        blocked_queue_count = 0

        for hostname in hosts:
            result = session.execute(
                text(
                    """
                    UPDATE crawl_queue
                    SET status = 'blocked'
                    WHERE status = 'pending'
                      AND (
                        lower(url) LIKE :host
                        OR lower(url) LIKE :www_host
                      )
                    """
                ),
                {
                    "host": f"%://{hostname}%",
                    "www_host": f"%://www.{hostname}%",
                },
            )
            blocked_queue_count += result.rowcount or 0

        session.commit()

        print(f"Blocked hosts: {len(hosts)}")
        print(f"Blocked URLs: {len(urls)}")
        print(f"Pending crawl queue entries blocked: {blocked_queue_count}")

    finally:
        session.close()


if __name__ == "__main__":
    sync_rejected_blocklist()
