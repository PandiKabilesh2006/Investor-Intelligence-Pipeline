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

cur.execute(
    """
    SELECT COUNT(*)
    FROM investors
    WHERE LOWER(COALESCE(website, '')) LIKE '%mock%'
       OR firm_name ~ ' [0-9]{3}$'
    """
)

print("Mock-looking investors:", cur.fetchone()[0])

cur.execute(
    """
    SELECT id, firm_name, website
    FROM investors
    WHERE LOWER(COALESCE(website, '')) LIKE '%mock%'
       OR firm_name ~ ' [0-9]{3}$'
    ORDER BY firm_name
    LIMIT 20
    """
)

for investor_id, firm_name, website in cur.fetchall():
    print(f"{investor_id}: {firm_name} | {website}")

cur.close()
conn.close()
