# Škola Online API (Bakaláři Timetable Parser)

Backendové API pro **získávání, parsování a ukládání veřejných rozvrhů z Bakalářů**.
Zaměření: vytáhnout z veřejných rozvrhů to, co je často schované za „Výuka“.

Primární use-case (protože lidi milují kafe víc než kalendáře):
- **učitel A + učitel B → nejbližší společné volno**

Aktuálně je hotové robustní jádro: **stahování HTML + parsování rozvrhu učitele + endpointy pro volné sloty**.

---

## Co to dělá

- 🔍 Stáhne veřejný rozvrh (HTML) pro učitele / týden
- 🧠 Naparsuje HTML do struktury: dny → hodiny → obsazeno/neobsazeno
- 🗂️ Uloží záznam importu (snapshot) do SQLite
- 🚀 Nabídne REST API (FastAPI) pro dotazy typu „kde učí“ a „kdy má volno“
- 🐳 Je to použitelné na Dockeru i na Synology

---

## Technologie

- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2.x
- SQLite (`timetable.db`)
- requests
- BeautifulSoup4 + lxml

---

## Struktura projektu (typicky)

```
app/
  main.py        # FastAPI aplikace + endpointy
  db.py          # SQLAlchemy engine + SessionLocal + get_db
  models.py      # SQLAlchemy modely
  parser.py      # parsování HTML z Bakalářů
requirements.txt
```

---

## Databázový model

### Snapshot
Uchovává informaci o tom, že proběhlo stažení/import.

| sloupec | typ | popis |
|---|---|---|
| id | int | primární klíč |
| week_type | str | interní tag: např. `current` / `next` |
| created_at | datetime | čas vytvoření |
| note | str | volitelná poznámka |

### RoomTeacherMap (pokud používáš mapování místností)
Mapuje **místnost → učitel → konkrétní čas** (heuristika/skóre).

| sloupec | typ | popis |
|---|---|---|
| room_id | str | ID místnosti (např. `06`) |
| week | str | `actual` / `next` |
| day_index | int | 1=Po … 5=Pá |
| lesson | int | číslo hodiny (0..14 podle školy) |
| teacher_id | str | ID učitele (např. `UL00R`) |
| teacher_name | str | jméno učitele (pokud známe) |
| score | int | skóre shody (vyšší = jistější) |
| updated_at | datetime | poslední aktualizace |

Unikátní klíč: `(room_id, week, day_index, lesson)`

---

## Konfigurace

V `app/main.py` je base URL školy typicky napevno jako:
- `BASE = "https://..."`

Doporučení (aby to bylo přenositelné): převeď na env proměnnou.

| proměnná | default | význam |
|---|---|---|
| `BAKALARI_BASE` | (hardcoded) | base URL školy |
| `DB_URL` | `sqlite:///./timetable.db` | SQLAlchemy URL |
| `TZ` | `Europe/Prague` | časové pásmo serveru (Docker/Synology) |

---

# API

Base path: **`/api/v1`**

Níže jsou endpointy podle aktuálního `app/main.py`.

> Drobnost: ve verzi, kterou mám nahranou tady, jsou v `main.py` **duplicitní definice** `GET /teacher/{teacher_id}/next-free-now`. V README popisuju jednu „správnou“ variantu (s parametrem `week`). V repu si nech jen jednu, jinak si koleduješ o runtime chaos.

---

## 0) Healthcheck

### `GET /api/v1/health`

Rychlý ping.

**200 OK**
```json
{ "status": "ok" }
```

---

## 1) Import snapshotu (stažení HTML)

### `POST /api/v1/import`

Stáhne stránku rozvrhu a uloží záznam do tabulky `snapshots`.

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `week_type` | string | `current` | interní tag importu (`current`, `next`, cokoliv) |

**Příklad**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/import?week_type=current"
```

**200 OK**
```json
{ "status": "ok", "snapshot_id": 1 }
```

---

## 2) Debug: stažené HTML učitele (head)

### `GET /api/v1/debug/teacher-html`

Vrátí metadata + prvních ~500 znaků HTML. Hodí se při rozbití parseru.

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `teacher_id` | string | `UX03T` | ID učitele |
| `week` | string | `actual` | `actual` nebo `next` |

**200 OK**
```json
{
  "url": "https://.../Timetable/Public/Actual/Teacher/UX03T",
  "status_code": 200,
  "content_type": "text/html; charset=utf-8",
  "html_length": 12345,
  "html_head": "<!doctype html>..."
}
```

---

## 3) Debug: parsovaná mřížka učitele (zkráceně)

### `GET /api/v1/debug/teacher-grid`

Vrátí zkrácený výstup parseru, ať vidíš, že se čte správný týden.

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `teacher_id` | string | `UX03T` | ID učitele |
| `week` | string | `actual` | `actual` nebo `next` |

**200 OK (příklad)**
```json
{
  "url": "https://.../Timetable/Public/Actual/Teacher/UX03T",
  "hour_columns": [{"lesson_number": 0, "time_text": "0 7:10 - 7:55"}],
  "rows_count": 5,
  "first_row": {
    "day_code": "po",
    "date_text": "6.1.",
    "cells": []
  }
}
```

---

## 4) Kde učitel učí v konkrétní čas

### `GET /api/v1/teacher/{teacher_id}/at`

Zjistí, jestli učitel v daný den/hodinu učí.

**Path parametry**

| parametr | typ | popis |
|---|---|---|
| `teacher_id` | string | ID učitele |

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `day_index` | int | (povinné) | 1=Po … 5=Pá |
| `lesson` | int | (povinné) | číslo hodiny |
| `week` | string | `actual` | `actual` nebo `next` |

**Příklad**
```bash
curl "http://127.0.0.1:8000/api/v1/teacher/UX03T/at?day_index=1&lesson=2&week=actual"
```

**200 OK**
```json
{
  "teacher_id": "UX03T",
  "week": "actual",
  "day_index": 1,
  "day_code": "po",
  "date_text": "6.1.",
  "lesson": 2,
  "time_text": "2 9:00 - 9:45",
  "is_teaching": false,
  "detail": {
    "lesson_number": 2,
    "is_teaching": false,
    "raw": "..."
  }
}
```

**Chyby**
```json
{ "error": "day_index out of range", "rows_count": 5 }
```
```json
{ "error": "lesson not found" }
```

---

## 5) Najdi první volno v týdnu (naivní)

### `GET /api/v1/teacher/{teacher_id}/next-free`

Projede rozvrh od pondělí ráno a vrátí první volnou buňku.

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `week` | string | `actual` | `actual` nebo `next` |

**200 OK**
```json
{
  "teacher_id": "UX03T",
  "week": "actual",
  "day_index": 1,
  "day_code": "po",
  "date_text": "6.1.",
  "lesson": 0,
  "time_text": "0 7:10 - 7:55"
}
```

**Když není volno**
```json
{ "error": "no free slot found" }
```

---

## 6) Najdi nejbližší volno od aktuálního času (doporučeno)

### `GET /api/v1/teacher/{teacher_id}/next-free-now`

Najde nejbližší volný slot „od teď“.

**Query parametry**

| parametr | typ | default | popis |
|---|---|---:|---|
| `week` | string | `actual` | `actual` nebo `next` |

**Poznámky**
- `date_text` z Bakalářů (např. `6.1.`) se skládá s aktuálním rokem serveru.
- Na Synology/Dockeru nastav `TZ=Europe/Prague`, ať ti to nehledá „volno“ včera.

**200 OK**
```json
{
  "teacher_id": "UX03T",
  "week": "actual",
  "day_index": 2,
  "day_code": "út",
  "date_text": "7.1.",
  "lesson": 4,
  "time_text": "4 11:00 - 11:45"
}
```

**Když není volno**
```json
{ "error": "no upcoming free slot found" }
```

---

# Cache a výkon

Bakaláři: stahování + parsing není zadarmo. Pokud nechceš, aby endpointy trvaly 5–10 s, udělej cache.

### Varianta A: cache v DB
- při volání endpointu nejdřív zkus DB
- pokud je záznam „fresh“ (např. mladší než 5 min), vrať DB
- jinak stáhni+naparsuj a ulož

### Varianta B: warm-up cache přes CRON
Tohle je ideální pro Synology:
- CRON (Task Scheduler) každých X minut zavolá endpointy, které chceš mít rychlé
- aplikace si tak sama připraví data dopředu

---

## Synology: CRON warm-up (Task Scheduler)

1) Vytvoř skript třeba `cache_warm.sh`
2) Nastav úlohu v DSM: **Ovládací panel → Plánovač úloh → Vytvořit → Naplánovaná úloha → Uživatelský skript**

### Příklad skriptu (`cache_warm.sh`)

- používá plné cesty
- loguje do souboru
- vrací `exit 0`

```bash
#!/bin/sh

# --- nastavení ---
API_BASE="http://127.0.0.1:8000"
LOG_DIR="/volume1/docker/skola-online-api/logs"
LOG_FILE="$LOG_DIR/cache_warm.log"

# Uprav si seznam učitelů podle reality
TEACHERS="UX03T UL00R"

mkdir -p "$LOG_DIR"

{
  echo "[cache_warm] start $(date)"

  for T in $TEACHERS; do
    echo "warming teacher=$T week=actual"
    /usr/bin/curl -sS "$API_BASE/api/v1/teacher/$T/next-free-now?week=actual" >/dev/null

    echo "warming teacher=$T week=next"
    /usr/bin/curl -sS "$API_BASE/api/v1/teacher/$T/next-free-now?week=next" >/dev/null
  done

  echo "[cache_warm] done $(date)"
  echo
} >> "$LOG_FILE" 2>&1

exit 0
```

### Doporučené rozvrhy úloh
- **každých 5 minut** (actual)
- **1× denně ráno** (next)

---

# Spuštění

## Lokálně

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

---

# Roadmap

## A7: Společné volno pro dva učitele (kafe-mode)

Návrh endpointu:

### `GET /api/v1/coffee/teachers/{teacher_a}/{teacher_b}/next-common-free`

**Query parametry (návrh)**

| parametr | typ | default | popis |
|---|---|---:|---|
| `weeks` | string | `actual,next` | které týdny prohledat |
| `from_now` | bool | `true` | filtrovat minulost |
| `limit` | int | 1 | vrať top N možností |

**Response (příklad)**
```json
{
  "teacher_a": "UX03T",
  "teacher_b": "UL00R",
  "week_used": "actual",
  "slot": {
    "day_index": 2,
    "day_code": "út",
    "date_text": "7.1.",
    "lesson": 5,
    "time_text": "5 12:00 - 12:45"
  }
}
```

---

## Licence a odpovědnost

Projekt je určen hlavně pro interní/vzdělávací použití.
Používání veřejných dat z Bakalářů je na odpovědnosti uživatele.

---

## Jak moc je to hotové?

**Úspěšnost realizace: 90 %**

Chybí hlavně:
- cache vrstva (aby endpointy nebyly pomalé)
- A7 (společné volno dvou učitelů)

Zbytek je už normální backend, žádná školní hračka.
