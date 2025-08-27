# ---------- Base Image ----------
FROM python:3.10-slim

# ---------- Environment Settings ----------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---------- Working Directory ----------
WORKDIR /app

# ---------- System Dependencies ----------
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- Install Python Dependencies ----------
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------- Copy Project Files ----------
COPY . /app/

# ---------- Collect Static Files ----------
RUN python manage.py collectstatic --noinput || true

# ---------- Gunicorn Run Command ----------
CMD ["gunicorn", "main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers=4", "--threads=4"]
