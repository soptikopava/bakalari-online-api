import requests

BASE_URL = "https://bakalari.zemedelka-opava.cz/Timetable/Public/"

def fetch_public_page() -> str:
    # For now just fetch landing page HTML.
    # Later: simulate selecting teacher/class/room + week mode (current/next) and fetch timetable HTML.
    r = requests.get(BASE_URL, timeout=30)
    r.raise_for_status()
    return r.text
