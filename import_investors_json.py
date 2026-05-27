import json
import sys
from pathlib import Path

import psycopg2
from pgvector.psycopg2 import register_vector

from app.config.settings import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)
from insert_into_db import insert_investor_data


def load_records(input_path):
    data = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, list):
        raise ValueError(
            "Import file must contain a JSON array of investor records"
        )

    return data


def is_valid_record(record):
    if not isinstance(record, dict):
        return False

    firm = str(
        record.get("firm", "")
    ).strip()

    return bool(firm)


def import_investors(input_path):
    records = load_records(input_path)

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    register_vector(conn)

    inserted_or_updated = 0
    skipped = 0
    failed = 0

    try:
        for record in records:
            if not is_valid_record(record):
                skipped += 1
                continue

            try:
                success = insert_investor_data(
                    record,
                    conn=conn,
                )

                if success:
                    inserted_or_updated += 1
                else:
                    skipped += 1

            except Exception as error:
                failed += 1
                print(
                    f"Failed importing {record.get('firm', '')}: {error}"
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "Import complete | "
        f"inserted_or_updated={inserted_or_updated} | "
        f"skipped={skipped} | "
        f"failed={failed}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python import_investors_json.py exports/investors_export.json"
        )

    import_investors(
        Path(sys.argv[1])
    )
