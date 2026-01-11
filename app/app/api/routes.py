from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.models import Teacher
from app.importer.import_run import run_import

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/teachers")
def list_teachers(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).order_by(Teacher.name.asc()).all()
    return [{"id": t.id, "name": t.name, "short": t.short} for t in teachers]

@router.post("/import")
def trigger_import(db: Session = Depends(get_db)):
    run_import(db, week_type="current")
    return {"status": "import triggered"}
