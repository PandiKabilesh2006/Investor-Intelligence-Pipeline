import psycopg2
import sys
from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()
delete_single_word = "--delete-single-word" in sys.argv

# Count bad rows before
cur.execute("SELECT COUNT(*) FROM partners WHERE name ~ E'^Partner\\\\s+[0-9]+$'")
print("Fake 'Partner N' rows to delete:", cur.fetchone()[0])

# Delete fake "Partner 7" style rows
cur.execute("DELETE FROM partners WHERE name ~ E'^Partner\\\\s+[0-9]+$'")

if delete_single_word:
    cur.execute("SELECT COUNT(*) FROM partners WHERE name NOT LIKE '% %'")
    print("Single-word name rows to delete:", cur.fetchone()[0])

    # Optional cleanup for legacy bad data. Use only after reviewing DB samples.
    cur.execute("DELETE FROM partners WHERE name NOT LIKE '% %'")

conn.commit()
print("\nCleanup done!")

# Count after
cur.execute("SELECT COUNT(*) FROM partners")
print("Real partners remaining:", cur.fetchone()[0])

# Show sample
cur.execute("""
    SELECT i.firm_name, p.name
    FROM partners p
    JOIN investors i ON i.id = p.investor_id
    ORDER BY i.firm_name
    LIMIT 30
""")
rows = cur.fetchall()
print("\nSample real partners:")
for r in rows:
    print(f"  {r[0]} -> {r[1]}")

conn.close()
