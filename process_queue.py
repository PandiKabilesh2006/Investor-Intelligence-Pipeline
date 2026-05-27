import subprocess
import sys

def main():
    print("\n================================================================================")
    print("STEP 1: Crawling 100 queued pending URLs...")
    print("================================================================================\n")
    
    # Run pipeline with a query that returns no search results to bypass search and process the queue
    subprocess.run(
        [sys.executable, "-u", "run_pipeline.py", "dummy_bypass_search_query_123"],
        check=True
    )
    
    print("\n================================================================================")
    print("STEP 2: Parsing newly extracted markdown files...")
    print("================================================================================\n")
    
    subprocess.run(
        [sys.executable, "-u", "parse_markdown.py"],
        check=True
    )
    
    print("\n================================================================================")
    print("STEP 3: Syncing parsed data to Postgres database...")
    print("================================================================================\n")
    
    subprocess.run(
        [sys.executable, "-u", "insert_into_db.py"],
        check=True
    )
    
    print("\n================================================================================")
    print("QUEUE INGESTION SEQUENCE SUCCESSFULLY COMPLETED")
    print("================================================================================\n")

if __name__ == "__main__":
    main()
