import re
from datetime import datetime, timezone

from sqlalchemy import or_

from app.database.db import SessionLocal
from app.database.models import ReviewQueue


def enqueue_review_item(
    url="",
    firm_name="",
    source_text="",
    extracted_payload=None,
    ai_decision="needs_review",
    ai_confidence=0.0,
    ai_reason="",
):
    db = SessionLocal()

    try:
        existing = (
            db.query(ReviewQueue)
            .filter(ReviewQueue.url == url)
            .filter(ReviewQueue.status == "pending")
            .first()
        )

        if existing:
            return existing

        item = ReviewQueue(
            url=url,
            firm_name=firm_name,
            source_text=source_text,
            extracted_payload=extracted_payload or {},
            ai_decision=ai_decision,
            ai_confidence=ai_confidence,
            ai_reason=ai_reason,
            status="pending",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    finally:
        db.close()


def _tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2
    }


def _score_example(example, query_text):
    haystack = " ".join(
        [
            example.url or "",
            example.firm_name or "",
            example.source_text or "",
            example.ai_reason or "",
            example.human_reason or "",
            example.reviewer_notes or "",
        ]
    )
    query_tokens = _tokens(query_text)
    haystack_tokens = _tokens(haystack)

    if not query_tokens or not haystack_tokens:
        return 0

    return len(query_tokens & haystack_tokens)


def get_review_examples(query_text="", limit=5):
    db = SessionLocal()

    try:
        examples = (
            db.query(ReviewQueue)
            .filter(ReviewQueue.status.in_(["approved", "rejected"]))
            .order_by(ReviewQueue.reviewed_at.desc().nullslast())
            .limit(100)
            .all()
        )

        ranked = sorted(
            examples,
            key=lambda item: _score_example(item, query_text),
            reverse=True,
        )

        return ranked[:limit]

    except Exception:
        return []

    finally:
        db.close()


def format_review_examples_for_prompt(query_text="", limit=5):
    examples = get_review_examples(query_text=query_text, limit=limit)

    if not examples:
        return "No human-reviewed examples are available yet."

    lines = []

    for example in examples:
        label = example.human_label or example.status
        reason = example.human_reason or example.reviewer_notes or example.ai_reason or ""
        lines.append(
            (
                f"- URL: {example.url or 'N/A'}\n"
                f"  Firm: {example.firm_name or 'N/A'}\n"
                f"  Human label: {label}\n"
                f"  Human reason: {reason}"
            )
        )

    return "\n".join(lines)


def mark_reviewed(item, label, reason="", notes=""):
    item.status = "approved" if label == "approved" else "rejected"
    item.human_label = label
    item.human_reason = reason
    item.reviewer_notes = notes
    item.reviewed_at = datetime.now(timezone.utc)
    return item
