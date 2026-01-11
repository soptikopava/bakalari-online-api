FROM python:3.12-slim

WORKDIR /app

# system deps (většinou netřeba, ale ať máš klid)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY timetable_sync /app/timetable_sync

ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Prague

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "timetable_sync.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
