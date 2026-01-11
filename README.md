# Škola Online API

Backendové API pro **získávání, parsování a ukládání veřejných rozvrhů z Bakalářů**
se zaměřením na **mapování místnost → učitel → čas**.

Projekt vznikl z praktické potřeby:
> rychle zjistit, **kdo kde učí**, i když veřejný rozvrh tuto informaci přímo nezobrazuje.

---

## Hlavní funkce

- 🔍 Stahuje veřejné rozvrhy Bakalářů (místnosti, učitelé, týdny)
- 🧠 Parsuje HTML rozvrh do strukturovaných dat
- 🔗 Páruje místnost s učitelem pomocí heuristiky a skóre shody
- 🗂️ Ukládá výsledky do databáze (SQLite)
- 🚀 Poskytuje REST API (FastAPI)
- 🐳 Připraveno pro Docker / Synology / server

---

## API – Přehled endpointů

- GET /api/v1/rooms
- GET /api/v1/teachers
- GET /api/v1/room/{room_id}/next
- GET /api/v1/room/{room_id}/next-with-teacher
- GET /api/v1/teacher/{teacher_id}/at
- GET /api/v1/teacher/{teacher_id}/next-free

---

## Cache & CRON

API podporuje cache přes pravidelné spouštění skriptu (např. CRON na Synology).

---

## Spuštění

pip install -r requirements.txt
uvicorn app.main:app --reload

---

## Licence

Pouze vzdělávací a nekomerční použití.
