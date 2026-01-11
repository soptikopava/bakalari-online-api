from bs4 import BeautifulSoup
import re

CELL_RE = re.compile(r"\s+")

def parse_percent(style: str, key: str) -> float | None:
    if not style:
        return None
    for part in style.split(";"):
        part = part.strip()
        if part.startswith(key):
            value = part.split(":")[1].strip()
            return float(value.replace("%", ""))
    return None


def parse_cell_text(text: str) -> dict:
    clean = CELL_RE.sub(" ", text.strip())
    parts = clean.split(" ")

    result = {
        "raw": clean,
        "class": None,
        "group": None,
        "room": None,
        "subject": None,
        "extra": [],
    }

    if len(parts) >= 1:
        result["class"] = parts[0]
    if len(parts) >= 3:
        result["group"] = parts[1]
        result["room"] = parts[2]
    if len(parts) >= 4:
        result["subject"] = parts[3]
    if len(parts) > 4:
        result["extra"] = parts[4:]

    return result


def parse_hour_columns(html: str) -> list[dict]:
    """
    Najde horní hlavičku hodin: .bk-hour-wrapper
    Vrátí list dictů:
      {left, lesson_number, time_text}
    """
    soup = BeautifulSoup(html, "lxml")
    cols = []
    for el in soup.select(".bk-hour-wrapper"):
        style = el.get("style", "")
        left = parse_percent(style, "left")
        text = el.get_text(" ", strip=True)

        # text vypadá třeba: "3 9:55 - 10:40"
        # první token je číslo hodiny
        lesson_number = None
        if text:
            first = text.split(" ", 1)[0]
            if first.isdigit():
                lesson_number = int(first)

        if left is not None and lesson_number is not None:
            cols.append({
                "left": left,
                "lesson_number": lesson_number,
                "time_text": text,
            })

    # seřadit podle left
    cols.sort(key=lambda x: x["left"])
    return cols


def nearest_lesson(left: float, cols: list[dict]) -> int | None:
    """
    Podle left% najde nejbližší sloupec z hlavičky.
    """
    if left is None or not cols:
        return None
    best = min(cols, key=lambda c: abs(c["left"] - left))
    return best["lesson_number"]


def parse_teacher_grid(html: str) -> dict:
    """
    Vrátí:
      - hour_columns (mapa sloupců)
      - rows: pro každý řádek seznam buněk s lesson_number + teaching + parsed text
    """
    soup = BeautifulSoup(html, "lxml")
    cols = parse_hour_columns(html)

    rows_out = []
    rows = soup.select(".bk-timetable-row")

    for row_index, row in enumerate(rows, start=1):
        # Pokus o získání popisku řádku (den/datum) – zatím debug
        row_text = row.get_text(" ", strip=True)
        # typicky začíná: "po 5.1."
        parts = row_text.split(" ")
        day_code = parts[0] if len(parts) > 0 else None
        date_text = parts[1] if len(parts) > 1 else None
        
        row_label = f"{day_code} {date_text}" if day_code and date_text else row_text[:40]


        cells = []
        for cell in row.select(".bk-timetable-cell"):
            cell_text = cell.get_text(" ", strip=True)  # může být prázdné!
            style = cell.get("style", "")
            left = parse_percent(style, "left")

            lesson_num = nearest_lesson(left, cols) if left is not None else None

            if cell_text:
                parsed = parse_cell_text(cell_text)
                is_teaching = True
            else:
                parsed = {"raw": "", "class": None, "group": None, "room": None, "subject": None, "extra": []}
                is_teaching = False

            cells.append({
                "lesson_number": lesson_num,
                "left": left,
                "is_teaching": is_teaching,
                **parsed
            })

        # nech jen buňky, co mají lesson_number (abychom neměli bordel)
        cells = [c for c in cells if c["lesson_number"] is not None]
        cells.sort(key=lambda c: c["lesson_number"])

        rows_out.append({
            "row_index": row_index,
            "day_code": day_code,
            "date_text": date_text,
            "cells": cells
        })


    return {
        "hour_columns": cols,
        "rows": rows_out
    }

import datetime as dt

TIME_RE = re.compile(r"^\d+\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$")

def parse_time_range(time_text: str) -> tuple[dt.time, dt.time] | None:
    """
    "3 9:55 - 10:40" -> (09:55, 10:40)
    """
    m = TIME_RE.match(time_text.strip())
    if not m:
        return None
    start_s, end_s = m.group(1), m.group(2)
    sh, sm = start_s.split(":")
    eh, em = end_s.split(":")
    return (dt.time(int(sh), int(sm)), dt.time(int(eh), int(em)))

def parse_select_options(html: str, select_id: str) -> list[dict]:
    """
    Vytáhne <option> z <select id="...">.
    Vrací [{id, name}]
    """
    soup = BeautifulSoup(html, "lxml")
    sel = soup.select_one(f"select#{select_id}")
    if not sel:
        return []
    out = []
    for opt in sel.select("option"):
        val = (opt.get("value") or "").strip()
        name = opt.get_text(" ", strip=True)
        if not val or not name:
            continue
        out.append({"id": val, "name": name})
    return out

def parse_teachers_list(html: str) -> list[dict]:
    return parse_select_options(html, "selectedTeacher")

