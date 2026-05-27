import psycopg2

from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


DEMO_FIRMS = [
    "a16z",
    "GV",
    "Bessemer",
    "Accel",
    "Greylock Partners",
    "Lightspeed Venture Partners",
    "Benchmark",
    "First Round",
]


conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)

cur = conn.cursor()

print("Source-backed investors:")
cur.execute(
    """
    SELECT COUNT(*)
    FROM investors
    WHERE source_url IS NOT NULL
      AND source_url <> ''
    """
)
print(cur.fetchone()[0])

print("\nDemo firms:")
for firm in DEMO_FIRMS:
    cur.execute(
        """
        SELECT
            i.id,
            i.firm_name,
            i.website,
            i.source_url,
            COUNT(DISTINCT p.id) AS partner_count,
            COUNT(DISTINCT pc.id) AS portfolio_count
        FROM investors i
        LEFT JOIN partners p ON p.investor_id = i.id
        LEFT JOIN portfolio_companies pc ON pc.investor_id = i.id
        WHERE LOWER(i.firm_name) = LOWER(%s)
        GROUP BY i.id, i.firm_name, i.website, i.source_url
        """,
        (firm,),
    )
    row = cur.fetchone()
    if not row:
        print(f"missing | {firm}")
        continue

    print(
        f"{row[0]} | {row[1]} | partners={row[4]} | "
        f"portfolio={row[5]} | source={row[3]}"
    )

print("\nPotentially older/non-provenance investors:")
cur.execute(
    """
    SELECT id, firm_name, website
    FROM investors
    WHERE source_url IS NULL
       OR source_url = ''
    ORDER BY firm_name
    LIMIT 30
    """
)
for investor_id, firm_name, website in cur.fetchall():
    print(f"{investor_id} | {firm_name} | {website}")

cur.close()
conn.close()
