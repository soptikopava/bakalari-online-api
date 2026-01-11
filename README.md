# Škola Online API

Backendové API pro **získávání, parsování a ukládání veřejných rozvrhů z Bakalářů**,  
se zaměřením na **mapování místnost → učitel → čas**.

Projekt vznikl z praktické potřeby:

> rychle zjistit, **kdo kde učí**, i když veřejný rozvrh tuto informaci přímo nezobrazuje.

---

## Hlavní funkce

- 🔍 Stahuje veřejné rozvrhy Bakalářů (místnosti, učitelé, týdny)
- 🧠 Parsuje HTML rozvrh do strukturovaných dat
- 🔗 Páruje **místnost s učitelem** pomocí heuristiky a skóre shody
- 🗂️ Ukládá výsledky do databáze (SQLite)
- 🚀 Poskytuje REST API (FastAPI)
- 🐳 Připraveno pro Docker / Synology / server

---

## Technologie

- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- SQLite
- BeautifulSoup + lxml
- Uvicorn
- Docker

---

## Databázový model

### Snapshot

Uchovává informaci o tom, **pro jaký týden byl rozvrh zpracován**.

| sloupec | popis |
|-------|------|
| id | primární klíč |
| week_type | `actual` / `next` |
| created_at | čas vytvoření |
| note | volitelná poznámka |

---

### RoomTeacherMap

Mapuje **místnost → učitele → konkrétní čas**.

Unikátní kombinace:
`room_id + week + day_index + lesson`

| sloupec | popis |
|-------|------|
| room_id | ID místnosti (např. `06`) |
| week | `actual` / `next` |
| day_index | den v týdnu (1 = Po … 5 = Pá) |
| lesson | číslo hodiny |
| teacher_id | ID učitele |
| teacher_name | jméno učitele |
| score | skóre shody |
| updated_at | poslední aktualizace |

---

## API – Přesný popis

### Seznam místností

GET `/api/v1/rooms`

### Seznam učitelů

GET `/api/v1/teachers`

### Nejbližší výuka v místnosti

GET `/api/v1/room/{room_id}/next`

### Nejbližší výuka v místnosti včetně učitele

GET `/api/v1/room/{room_id}/next-with-teacher`

---

## Cache a CRON (doporučené nastavení)

Některé endpointy (zejména `next-with-teacher`) mohou při živém parsování trvat několik sekund.
Proto je doporučeno **předpočítávat data pomocí CRON úlohy**.

### Doporučený postup

- pravidelně (např. každých 30–60 minut) spustit endpoint pro aktualizaci snapshotu
- data se uloží do databáze a API pak pouze čte cache

### Příklad CRON úlohy (Linux / Synology)

```bash
*/30 * * * * curl -X POST http://localhost:8000/api/v1/import?week_type=actual
*/30 * * * * curl -X POST http://localhost:8000/api/v1/import?week_type=next
```

### Výhody

- ⚡ rychlé odpovědi API (ms místo sekund)
- 📉 minimální zátěž serveru
- 🧠 konzistentní data v průběhu dne

---

## Spuštění projektu

### Lokálně

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API poběží na:
http://127.0.0.1:8000

Swagger dokumentace:
http://127.0.0.1:8000/docs

---

## Docker / Synology

- aplikace očekává kód v `/app`
- databáze `timetable.db` se vytváří automaticky
- vhodné pro dlouhodobý běh na NASu

---

## Stav projektu

- ✔ parser hotový
- ✔ databázový model hotový
- ✔ API hotové
- ✔ Docker běh ověřen
- 🔜 cache optimalizace (plně automatická)

---

## Licence

Projekt je určen pro **vzdělávací a nekomerční použití**.
Používání dat z Bakalářů je na odpovědnosti uživatele.
