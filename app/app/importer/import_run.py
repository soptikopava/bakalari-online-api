from datetime import datetime
from sqlalchemy.orm import Session
from app.core.models import Snapshot
from app.importer.fetch import fetch_public_page

def run_import(db: Session, week_type: str = "current") -> int:
    """
    Run one import cycle. For now it just downloads the public page.
    Later it will:
      - fetch list of teachers/classes/rooms
      - fetch timetable for each entity for week_type
      - parse lessons
      - upsert lessons into DB
    Returns count of parsed items (placeholder).
    """
    snap = Snapshot(week_type=week_type, status="running", note="bootstrap import")
    db.add(snap)
    db.commit()
    db.refresh(snap)

    try:
        html = fetch_public_page()
        # placeholder: store note length so we see it worked
        snap.note = f"Downloaded HTML length={len(html)}"
        snap.status = "ok"
        snap.finished_at = datetime.utcnow()
        db.commit()
        return 0
    except Exception as e:
        snap.status = "fail"
        snap.note = f"Import failed: {e!r}"
        snap.finished_at = datetime.utcnow()
        db.commit()
        raise
