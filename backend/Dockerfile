FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev \
    libcairo2 shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# EXIGENCES=prod pour la production (gunicorn, redis), dev par défaut (outils de test).
ARG EXIGENCES=dev
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/${EXIGENCES}.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
