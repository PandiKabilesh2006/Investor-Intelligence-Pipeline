import sys
from urllib.parse import urlparse

from sqlalchemy import text

from app.database.db import SessionLocal
from app.database.models import Investor, Partner, PortfolioCompany


def _host(url):
    try:
        hostname = (urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def _matches_blocked_host(hostname, blocked_hosts):
    return any(
        hostname == blocked_host
        or hostname.endswith(f".{blocked_host}")
        for blocked_host in blocked_hosts
    )


def load_blocked_hosts(session):
    rows = session.execute(
        text(
            """
            SELECT url
            FROM failed_urls
            WHERE status = 'blocked'
            """
        )
    ).fetchall()
    hosts = set()

    for row in rows:
        hostname = _host(row[0])

        if hostname:
            hosts.add(hostname)

    return hosts


def find_blocked_investors(session, blocked_hosts):
    matches = []

    for investor in session.query(Investor).all():
        website_host = _host(investor.website)
        source_host = _host(investor.source_url)

        investor_hosts = {website_host} if website_host else {source_host}
        investor_hosts = {host for host in investor_hosts if host}

        matched_hosts = sorted(
            host
            for host in investor_hosts
            if _matches_blocked_host(host, blocked_hosts)
        )

        if matched_hosts:
            matches.append((investor, matched_hosts))

    return matches


def remove_blocked_investors(apply=False):
    session = SessionLocal()

    try:
        blocked_hosts = load_blocked_hosts(session)
        matches = find_blocked_investors(session, blocked_hosts)

        print(f"Blocked hosts loaded: {len(blocked_hosts)}")
        print(f"Investor records matching blocklist: {len(matches)}")

        for investor, matched_hosts in matches[:100]:
            print(
                f"- #{investor.id} {investor.firm} | "
                f"{investor.website or investor.source_url or 'no url'} | "
                f"blocked: {', '.join(matched_hosts)}"
            )

        if not apply:
            print("\nDry run only. Apply with: python remove_blocked_investors.py --apply")
            return

        removed_partner_rows = 0
        removed_portfolio_rows = 0

        for investor, _matched_hosts in matches:
            removed_partner_rows += (
                session.query(Partner)
                .filter(Partner.investor_id == investor.id)
                .delete()
            )
            removed_portfolio_rows += (
                session.query(PortfolioCompany)
                .filter(PortfolioCompany.investor_id == investor.id)
                .delete()
            )
            session.delete(investor)

        session.commit()

        print("\nDeleted blocked investor records.")
        print(f"Investors deleted: {len(matches)}")
        print(f"Partner rows deleted: {removed_partner_rows}")
        print(f"Portfolio rows deleted: {removed_portfolio_rows}")

    finally:
        session.close()


if __name__ == "__main__":
    remove_blocked_investors(apply="--apply" in sys.argv)
