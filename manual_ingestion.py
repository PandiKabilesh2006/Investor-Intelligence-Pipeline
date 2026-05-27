import sys
import subprocess
import os

# Set standard UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if len(sys.argv) < 2:
    print("Error: Search query argument is required.")
    sys.exit(1)

query = sys.argv[1]

try:
    # 1. Run Crawler
    print(f"\n================================================================================")
    print(f"STEP 1: Starting Crawler for query: '{query}'")
    print(f"================================================================================\n")
    
    subprocess.run(
        [sys.executable, "-u", "run_pipeline.py", query],
        check=True
    )
    
    # 2. Run Parser
    print(f"\n================================================================================")
    print(f"STEP 2: Running LLM Parser on Extracted Content")
    print(f"================================================================================\n")
    
    subprocess.run(
        [sys.executable, "-u", "parse_markdown.py"],
        check=True
    )
    
    # 3. Sync to DB
    print(f"\n================================================================================")
    print(f"STEP 3: Syncing Parsed Data to Database")
    print(f"================================================================================\n")
    
    subprocess.run(
        [sys.executable, "-u", "insert_into_db.py"],
        check=True
    )
    
    print(f"\n================================================================================")
    print(f"MANUAL INGESTION SEQUENCE SUCCESSFULLY COMPLETED")
    print(f"================================================================================\n")

except subprocess.CalledProcessError as e:
    print(f"\nSubprocess failed: {e}")
    sys.exit(e.returncode)
except Exception as e:
    print(f"\nIngestion failed: {e}")
    sys.exit(1)
