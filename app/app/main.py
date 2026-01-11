from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
import requests

from app.db import engine, get_db, Base
from app.models import Snapshot, RoomTeacherMap
from app.parser import parse_teacher_grid

import datetime as dt
import time
from typing import Any

from app.parser import parse_time_range
from app.parser import parse_select_options

app = FastAPI(title="Skola Online API")

Base.metadata.create_all(bind=engine)

BASE = "https://bakalari.zemedelka-opava.cz"

_HTML_CACHE: dict[str, dict[str, Any]] = {}
_GRID_CACHE: dict[str, dict[str, Any]] = {}

def cached_get(url: str, ttl: int = 300) -> str:
    """
    Cache pro HTML (default 5 minut).
    """
    now_ts = time.time()
    hit = _HTML_CACHE.get(url)
    if hit and (now_ts - hit["ts"] < ttl):
        return hit["html"]

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    html = r.text
    _HTML_CACHE[url] = {"ts": now_ts, "html": html}
    return html

def cached_parse_grid(url: str, ttl: int = 300) -> dict:
    """
    Cache pro naparsovaný grid (default 5 minut).
    """
    now_ts = time.time()
    hit = _GRID_CACHE.get(url)
    if hit and (now_ts - hit["ts"] < ttl):
        return hit["grid"]

    html = cached_get(url, ttl=ttl)
    grid = parse_teacher_grid(html)
    _GRID_CACHE[url] = {"ts": now_ts, "grid": grid}
    return grid

_TEACHERS_CACHE = {"ts": 0.0, "data": []}

def fetch_room_url(room_id: str, week_part: str) -> str:
    return f"{BASE}/Timetable/Public/{week_part}/Room/{room_id}"

def fetch_teacher_url(teacher_id: str, week_part: str) -> str:
    return f"{BASE}/Timetable/Public/{week_part}/Teacher/{teacher_id}"

def get_teachers_cached(ttl_seconds: int = 600):
    now_ts = time.time()
    if _TEACHERS_CACHE["data"] and (now_ts - _TEACHERS_CACHE["ts"] < ttl_seconds):
        return _TEACHERS_CACHE["data"]

    r = requests.get(f"{BASE}/Timetable/Public/", timeout=30)
    r.raise_for_status()
    teachers = parse_select_options(r.text, "selectedTeacher")

    _TEACHERS_CACHE["ts"] = now_ts
    _TEACHERS_CACHE["data"] = teachers
    return teachers

def find_teacher_for_slot_old(day_index: int, lesson: int, room_name: str, subject: str | None, class_name: str | None, week_part: str):
    """
    Projede všechny učitele, stáhne jejich rozvrh a najde toho, kdo má v daný den+hodinu místnost a ideálně i předmět/třídu.
    Vrátí teacher_id nebo None.
    """
    # načteme seznam učitelů
    r = requests.get(f"{BASE}/Timetable/Public/", timeout=30)
    r.raise_for_status()
    teachers = parse_select_options(r.text, "selectedTeacher")

    best_match = None
    best_score = -1

    for t in teachers:
        teacher_id = t["id"]
        url = f"{BASE}/Timetable/Public/{week_part}/Teacher/{teacher_id}"
        rt = requests.get(url, timeout=30)
        if rt.status_code != 200:
            continue

        grid = parse_teacher_grid(rt.text)
        if day_index < 1 or day_index > len(grid["rows"]):
            continue

        row = grid["rows"][day_index - 1]
        cell = next((c for c in row["cells"] if c["lesson_number"] == lesson), None)
        if not cell or not cell["is_teaching"]:
            continue

        # scoring: místnost je must-have
        score = 0
        if (cell.get("room") or "").strip() == room_name.strip():
            score += 5
        else:
            continue

        # předmět + třída přidají jistotu
        if subject and cell.get("subject") == subject:
            score += 3
        if class_name and cell.get("class") == class_name:
            score += 2

        if score > best_score:
            best_score = score
            best_match = {
                "teacher_id": teacher_id,
                "teacher_name": t["name"],
                "score": score,
                "cell": cell,
            }

        # perfektní shoda? skonči
        if score >= 10:
            break

    return best_match

def find_teacher_for_slot(day_index: int, lesson: int, room_name: str, subject: str | None, class_name: str | None, week_part: str):
    teachers = get_teachers_cached()

    best = None
    best_score = -1

    for t in teachers:
        teacher_id = t["id"]
        t_url = fetch_teacher_url(teacher_id, week_part)
        try:
            tgrid = cached_parse_grid(t_url, ttl=300)
        except Exception:
            continue

        if day_index < 1 or day_index > len(tgrid["rows"]):
            continue

        row = tgrid["rows"][day_index - 1]
        cell = next((c for c in row["cells"] if c["lesson_number"] == lesson), None)
        if not cell or not cell["is_teaching"]:
            continue

        if (cell.get("room") or "").strip() != room_name.strip():
            continue

        score = 5
        if subject and cell.get("subject") == subject:
            score += 3
        if class_name and cell.get("class") == class_name:
            score += 2

        if score > best_score:
            best_score = score
            best = {
                "teacher_id": teacher_id,
                "teacher_name": t["name"],
                "score": score,
                "teacher_cell": cell,
            }

        if score >= 10:
            break

    return best


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/import")
def run_import(
    week_type: str = "current",
    db: Session = Depends(get_db),
):
    url = f"{BASE}/Timetable/Public/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    snap = Snapshot(
        week_type=week_type,
        note=f"Downloaded HTML length={len(r.text)}"
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    return {"status": "ok", "snapshot_id": snap.id}


@app.get("/api/v1/debug/teacher-html")
def debug_teacher_html(
    teacher_id: str = "UX03T",
    week: str = "actual",
):
    week_part = "Actual" if week.lower() == "actual" else "Next"
    url = f"{BASE}/Timetable/Public/{week_part}/Teacher/{teacher_id}"

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    return {
        "url": url,
        "status_code": r.status_code,
        "content_type": r.headers.get("content-type"),
        "html_length": len(r.text),
        "html_head": r.text[:500],
    }


@app.get("/api/v1/debug/teacher-grid")
def debug_teacher_grid(teacher_id: str = "UX03T", week: str = "actual"):
    week_part = "Actual" if week.lower() == "actual" else "Next"
    url = f"{BASE}/Timetable/Public/{week_part}/Teacher/{teacher_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    grid = parse_teacher_grid(r.text)
    return {
        "url": url,
        "hour_columns": grid["hour_columns"][:5],  # jen prvních 5 pro přehled
        "rows_count": len(grid["rows"]),
        "first_row": grid["rows"][0] if grid["rows"] else None,
    }

@app.get("/api/v1/teacher/{teacher_id}/at")
def teacher_at(teacher_id: str, day_index: int, lesson: int, week_type: str = "actual"):
    week_part = {"actual": "Actual", "next": "Next"}.get(week_type, "Actual")
    url = fetch_teacher_url(teacher_id, week_part)

    grid = cached_parse_grid(url, ttl=300)

    if day_index < 1 or day_index > len(grid["rows"]):
        return {"error": "day_index out of range", "day_index": day_index, "rows_count": len(grid["rows"])}

    row = grid["rows"][day_index - 1]
    cell = next((c for c in row["cells"] if c["lesson_number"] == lesson), None)
    if not cell:
        return {"error": "lesson not found", "lesson": lesson}

    col = next((x for x in grid["hour_columns"] if x["lesson_number"] == lesson), None)

    return {
        "teacher_id": teacher_id,
        "week": week_type,
        "day_index": day_index,
        "day_code": row.get("day_code"),
        "date_text": row.get("date_text"),
        "lesson": lesson,
        "time_text": col["time_text"] if col else None,
        "is_teaching": cell["is_teaching"],
        "detail": cell if cell["is_teaching"] else None,
        "url": url,
    }

@app.get("/api/v1/teacher/{teacher_id}/next-free")
def teacher_next_free(teacher_id: str, week: str = "actual"):
    week_part = "Actual" if week.lower() == "actual" else "Next"
    url = fetch_teacher_url(teacher_id, week_part)
    grid = cached_parse_grid(url, ttl=300)

    for day_i, row in enumerate(grid["rows"], start=1):
        for cell in row["cells"]:
            if cell["is_teaching"] is False:
                lesson = cell["lesson_number"]
                return {
                    "teacher_id": teacher_id,
                    "week": week.lower(),
                    "day_index": day_i,
                    "day_code": row.get("day_code"),
                    "date_text": row.get("date_text"),
                    "lesson": lesson,
                    "time_text": next((x["time_text"] for x in grid["hour_columns"] if x["lesson_number"] == lesson), None),
                }

    return {"error": "no free slot found"}

def find_next_free_from_html(html: str, now: dt.datetime):
    grid = parse_teacher_grid(html)

    # lesson_number -> (start_time, end_time)
    lesson_times = {}
    for col in grid["hour_columns"]:
        tr = parse_time_range(col["time_text"])
        if tr:
            lesson_times[col["lesson_number"]] = tr

    for day_i, row in enumerate(grid["rows"], start=1):
        if not row.get("date_text"):
            continue

        # date_text: "5.1." -> date(year, 1, 5)
        try:
            d, m = row["date_text"].replace(".", " ").split()[:2]
            date_obj = dt.date(now.year, int(m), int(d))
        except Exception:
            continue

        for cell in row["cells"]:
            if cell["is_teaching"]:
                continue

            lesson = cell["lesson_number"]
            if lesson not in lesson_times:
                continue

            start_t, _ = lesson_times[lesson]
            slot_dt = dt.datetime.combine(date_obj, start_t)

            if slot_dt >= now:
                return {
                    "day_index": day_i,
                    "day_code": row.get("day_code"),
                    "date_text": row.get("date_text"),
                    "lesson": lesson,
                    "time_text": next(
                        (x["time_text"] for x in grid["hour_columns"] if x["lesson_number"] == lesson),
                        None
                    ),
                }

    return None


@app.get("/api/v1/teacher/{teacher_id}/next-free-now")
def teacher_next_free_now(teacher_id: str):
    """
    Najde nejbližší volno od aktuálního času.
    Když v 'Actual' týdnu už nic není (víkend), zkusí 'Next'.
    """
    now = dt.datetime.now()

    for week_key, week_part in [("actual", "Actual"), ("next", "Next")]:
        url = fetch_teacher_url(teacher_id, week_part)
        html = cached_get(url, ttl=300)

        found = find_next_free_from_html(html, now)
        if found:
            return {
                "teacher_id": teacher_id,
                "week_used": week_key,
                **found,
            }

    return {"error": "no upcoming free slot found in actual nor next week"}

@app.get("/api/v1/rooms")
def list_rooms():
    """
    Seznam učeben dostupných ve veřejném rozvrhu.
    """
    url = f"{BASE}/Timetable/Public/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    rooms = parse_select_options(r.text, "selectedRoom")
    return {"count": len(rooms), "rooms": rooms}

@app.get("/api/v1/room/{room_id}/grid")
def room_grid(room_id: str, week_type: str = "actual"):
    week_part = {"actual": "Actual", "next": "Next"}.get(week_type, "Actual")

    url = fetch_room_url(room_id, week_part)
    grid = cached_parse_grid(url, ttl=300)

    return {
        "url": url,
        "room_id": room_id,
        "week": week_type,
        "hour_columns": grid["hour_columns"],
        "rows_count": len(grid["rows"]),
        "first_row": grid["rows"][0] if grid["rows"] else None,
    }

def find_current_slot_from_grid(grid: dict, now: dt.datetime):
    # map lesson -> (start,end)
    lesson_times = {}
    for col in grid["hour_columns"]:
        tr = parse_time_range(col["time_text"])
        if tr:
            lesson_times[col["lesson_number"]] = tr

    today = now.date()
    now_t = now.time()

    for row in grid["rows"]:
        if not row.get("date_text"):
            continue

        try:
            d, m = row["date_text"].replace(".", " ").split()[:2]
            date_obj = dt.date(now.year, int(m), int(d))
        except Exception:
            continue

        if date_obj != today:
            continue

        # jsme na správném dni
        for cell in row["cells"]:
            lesson = cell["lesson_number"]
            if lesson not in lesson_times:
                continue

            start_t, end_t = lesson_times[lesson]
            if start_t <= now_t <= end_t:
                return {
                        "day_index": row.get("row_index"),   # <- TOTO JE CELÝ FIX
                        "day_code": row.get("day_code"),
                        "date_text": row.get("date_text"),
                        "lesson": lesson,
                        "time_text": next((x["time_text"] for x in grid["hour_columns"] if x["lesson_number"] == lesson), None),
                        "is_teaching": cell["is_teaching"],
                        "detail": cell,
                }

    return None

@app.get("/api/v1/room/{room_id}/now")
def room_now(room_id: str):
    now = dt.datetime.now()

    # Nejprve zkus Actual, když to nic nenajde (víkend / mimo čas), zkus Next
    for week_key, week_part in [("actual", "Actual"), ("next", "Next")]:
        url = fetch_room_url(room_id, week_part)
        grid = cached_parse_grid(url, ttl=300)

        current = find_current_slot_from_grid(grid, now)
        if current:
            return {
                "room_id": room_id,
                "week_used": week_key,
                "url": url,
                **current,
            }

    return {
        "room_id": room_id,
        "error": "no current lesson (either weekend, outside lesson times, or no data for today)",
        "server_time": now.isoformat(timespec="seconds"),
    }

@app.get("/api/v1/teachers")
def list_teachers():
    url = f"{BASE}/Timetable/Public/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    teachers = get_teachers_cached()
    return {"count": len(teachers), "teachers": teachers}

@app.get("/api/v1/room/{room_id}/now-with-teacher")
def room_now_with_teacher(room_id: str):
    now = dt.datetime.now()

    # 1) zjisti current slot v místnosti (Actual -> Next fallback)
    current_pack = None
    current_url = None
    current_week_part = None
    current_week_key = None

    for week_key, week_part in [("actual", "Actual"), ("next", "Next")]:
        url = fetch_room_url(room_id, week_part)
        grid = cached_parse_grid(url, ttl=300)

        current = find_current_slot_from_grid(grid, now)
        if current:
            current_pack = current
            current_url = url
            current_week_part = week_part
            current_week_key = week_key
            break

    if not current_pack:
        return {
            "room_id": room_id,
            "error": "no current lesson (weekend / outside lesson times / no data for today)",
            "server_time": now.isoformat(timespec="seconds"),
        }

    if not current_pack.get("day_index"):
        return {"room_id": room_id, "error": "current slot missing day_index", "current": current_pack}

    room_name = (current_pack["detail"].get("room") or "").strip()
    subject = current_pack["detail"].get("subject")
    class_name = current_pack["detail"].get("class")

    # 2) seznam učitelů
    r = requests.get(f"{BASE}/Timetable/Public/", timeout=30)
    r.raise_for_status()
    teachers = parse_select_options(r.text, "selectedTeacher")

    best = None
    best_score = -1

    # 3) bruteforce match přes učitele
    for t in teachers:
        teacher_id = t["id"]

        t_url = fetch_teacher_url(teacher_id, current_week_part)
        try:
            tgrid = cached_parse_grid(t_url, ttl=300)
        except Exception:
            continue

        day_index = current_pack["day_index"]
        if day_index < 1 or day_index > len(tgrid["rows"]):
            continue

        row = tgrid["rows"][day_index - 1]
        cell = next((c for c in row["cells"] if c["lesson_number"] == current_pack["lesson"]), None)
        if not cell or not cell["is_teaching"]:
            continue

        # room must match
        if (cell.get("room") or "").strip() != room_name:
            continue

        score = 5  # room match
        if subject and cell.get("subject") == subject:
            score += 3
        if class_name and cell.get("class") == class_name:
            score += 2

        if score > best_score:
            best_score = score
            best = {
                "teacher_id": teacher_id,
                "teacher_name": t["name"],
                "score": score,
                "teacher_cell": cell,
            }

        if score >= 10:
            break

    return {
        "room_id": room_id,
        "week_used": current_week_key,
        "url": current_url,
        "current": current_pack,
        "teacher_match": best,
    }

def find_next_lesson_from_grid(grid: dict, now: dt.datetime):
    lesson_times = {}
    for col in grid["hour_columns"]:
        tr = parse_time_range(col["time_text"])
        if tr:
            lesson_times[col["lesson_number"]] = tr

    best = None
    best_dt = None

    for row in grid["rows"]:
        if not row.get("date_text"):
            continue

        try:
            d, m = row["date_text"].replace(".", " ").split()[:2]
            date_obj = dt.date(now.year, int(m), int(d))
        except Exception:
            continue

        for cell in row["cells"]:
            if not cell["is_teaching"]:
                continue

            lesson = cell["lesson_number"]
            if lesson not in lesson_times:
                continue

            start_t, _ = lesson_times[lesson]
            slot_dt = dt.datetime.combine(date_obj, start_t)

            if slot_dt >= now:
                if best_dt is None or slot_dt < best_dt:
                    best_dt = slot_dt
                    best = {
                        "day_index": row.get("row_index"),
                        "day_code": row.get("day_code"),
                        "date_text": row.get("date_text"),
                        "lesson": lesson,
                        "time_text": next((x["time_text"] for x in grid["hour_columns"] if x["lesson_number"] == lesson), None),
                        "detail": cell,
                    }

    return best


@app.get("/api/v1/room/{room_id}/next")
def room_next(room_id: str):
    now = dt.datetime.now()

    for week_key, week_part in [("actual", "Actual"), ("next", "Next")]:
        url = fetch_room_url(room_id, week_part)
        grid = cached_parse_grid(url, ttl=300)

        nxt = find_next_lesson_from_grid(grid, now)
        if nxt:
            return {
                "room_id": room_id,
                "week_used": week_key,
                "url": url,
                "next": nxt,
            }

    return {
        "room_id": room_id,
        "error": "no next lesson found (actual nor next)",
        "server_time": now.isoformat(timespec="seconds"),
    }

@app.get("/api/v1/room/{room_id}/next-with-teacher")
def room_next_with_teacher(room_id: str):
    now = dt.datetime.now()

    for week_key, week_part in [("actual", "Actual"), ("next", "Next")]:
        url = fetch_room_url(room_id, week_part)
        grid = cached_parse_grid(url, ttl=300)

        nxt = find_next_lesson_from_grid(grid, now)
        if not nxt:
            continue

        room_name = (nxt["detail"].get("room") or "").strip()
        subject = nxt["detail"].get("subject")
        class_name = nxt["detail"].get("class")

        match = find_teacher_for_slot(
            day_index=nxt["day_index"],
            lesson=nxt["lesson"],
            room_name=room_name,
            subject=subject,
            class_name=class_name,
            week_part=week_part,
        )

        return {
            "room_id": room_id,
            "week_used": week_key,
            "url": url,
            "next": nxt,
            "teacher_match": match,
        }

    return {
        "room_id": room_id,
        "error": "no next lesson found (actual nor next)",
        "server_time": now.isoformat(timespec="seconds"),
    }

@app.post("/api/v1/room/{room_id}/rebuild-map")
def rebuild_room_teacher_map(
    room_id: str,
    week: str = "next",        # default "next", protože o to ti jde
    db: Session = Depends(get_db),
):
    week_key = week.lower()
    week_part = "Actual" if week_key == "actual" else "Next"

    url = fetch_room_url(room_id, week_part)
    grid = cached_parse_grid(url, ttl=300)

    # projdeme všechny řádky (dny) a buňky (hodiny)
    upserts = 0
    for row in grid["rows"]:
        day_index = row.get("row_index")
        if not day_index:
            continue

        for cell in row["cells"]:
            if not cell.get("is_teaching"):
                continue

            lesson = cell["lesson_number"]
            room_name = cell.get("room") or ""     # v room gridu to bude třeba "U3"
            subject = cell.get("subject")
            class_name = cell.get("class")

            match = find_teacher_for_slot(
                day_index=day_index,
                lesson=lesson,
                room_name=room_name,
                subject=subject,
                class_name=class_name,
                week_part=week_part,
            )

            if not match:
                continue

            # UPSERT style: najdi existující řádek a přepiš
            stmt = select(RoomTeacherMap).where(
                RoomTeacherMap.room_id == room_id,
                RoomTeacherMap.week == week_key,
                RoomTeacherMap.day_index == day_index,
                RoomTeacherMap.lesson == lesson,
            )
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                existing.teacher_id = match["teacher_id"]
                existing.teacher_name = match.get("teacher_name")
                existing.score = match.get("score")
                existing.updated_at = dt.datetime.utcnow()
            else:
                db.add(RoomTeacherMap(
                    room_id=room_id,
                    week=week_key,
                    day_index=day_index,
                    lesson=lesson,
                    teacher_id=match["teacher_id"],
                    teacher_name=match.get("teacher_name"),
                    score=match.get("score"),
                    updated_at=dt.datetime.utcnow(),
                ))

            upserts += 1

    db.commit()
    return {"room_id": room_id, "week": week_key, "mapped_slots": upserts}

@app.get("/api/v1/room/{room_id}/next-from-map")
def room_next_from_map(room_id: str, week: str = "next", db: Session = Depends(get_db)):
    week_key = week.lower()
    week_part = "Actual" if week_key == "actual" else "Next"

    # 1) zjisti příští hodinu v místnosti (už máš endpoint logiku)
    url = fetch_room_url(room_id, week_part)
    grid = cached_parse_grid(url, ttl=300)

    # vezmeme "next" jako první teaching slot v týdnu (ty už máš něco podobného)
    # tady minimalisticky: najdi první teaching cell v gridu
    for row in grid["rows"]:
        for cell in row["cells"]:
            if cell.get("is_teaching"):
                day_index = row["row_index"]
                lesson = cell["lesson_number"]

                # 2) lookup v DB
                stmt = select(RoomTeacherMap).where(
                    RoomTeacherMap.room_id == room_id,
                    RoomTeacherMap.week == week_key,
                    RoomTeacherMap.day_index == day_index,
                    RoomTeacherMap.lesson == lesson,
                )
                mapped = db.execute(stmt).scalar_one_or_none()

                return {
                    "room_id": room_id,
                    "week": week_key,
                    "next": {
                        "day_index": day_index,
                        "day_code": row.get("day_code"),
                        "date_text": row.get("date_text"),
                        "lesson": lesson,
                        "detail": cell,
                    },
                    "teacher": None if not mapped else {
                        "teacher_id": mapped.teacher_id,
                        "teacher_name": mapped.teacher_name,
                        "score": mapped.score,
                        "updated_at": mapped.updated_at.isoformat(),
                    }
                }

    return {"error": "no teaching slot found"}

