# Reproducible run: same command on any machine, Chromium included.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCRAPER_HEADLESS=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY scraper ./scraper

# 30 pages x 10 records by default; override with: docker run ... run <spider> --pages N
ENTRYPOINT ["python", "-m", "scraper.cli"]
CMD ["run", "quotes", "--pages", "3"]
