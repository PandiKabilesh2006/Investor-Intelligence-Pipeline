from app.database.db import SessionLocal
from sqlalchemy import text

def check():
    session = SessionLocal()
    try:
        pending = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='pending'")).fetchone()[0]
        completed = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='completed'")).fetchone()[0]
        failed = session.execute(text("SELECT count(*) FROM crawl_queue WHERE status='failed'")).fetchone()[0]
        investors = session.execute(text("SELECT count(*) FROM investors")).fetchone()[0]
        
        print("Crawl Queue Status:")
        print(f"  Pending:   {pending}")
        print(f"  Completed: {completed}")
        print(f"  Failed:    {failed}")
        print(f"Investors in DB: {investors}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    check()
