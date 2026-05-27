import psycopg2

from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)

cur = conn.cursor()

for table in ("investors", "partners", "portfolio_companies"):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}: {cur.fetchone()[0]}")

print("\nSample investors with relationship counts:")
cur.execute(
    """
    SELECT
        i.id,
        i.firm_name,
        i.website,
        COUNT(DISTINCT p.id) AS partner_count,
        COUNT(DISTINCT pc.id) AS portfolio_count
    FROM investors i
    LEFT JOIN partners p ON p.investor_id = i.id
    LEFT JOIN portfolio_companies pc ON pc.investor_id = i.id
    GROUP BY i.id, i.firm_name, i.website
    ORDER BY partner_count DESC, portfolio_count DESC, i.firm_name ASC
    LIMIT 20
    """
)

for row in cur.fetchall():
    print(
        f"{row[0]} | {row[1]} | partners={row[3]} | "
        f"portfolio={row[4]} | {row[2]}"
    )

print("\nBad partner placeholders:")
cur.execute("SELECT COUNT(*) FROM partners WHERE name ~ E'^Partner\\\\s+[0-9]+$'")
print(cur.fetchone()[0])

print("\nMock-looking investors:")
cur.execute(
    """
    SELECT COUNT(*)
    FROM investors
    WHERE LOWER(COALESCE(website, '')) LIKE '%mock%'
       OR firm_name ~ ' [0-9]{3}$'
    """
)
print(cur.fetchone()[0])

cur.close()
conn.close()
