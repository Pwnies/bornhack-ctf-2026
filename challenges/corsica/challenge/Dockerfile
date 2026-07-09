# Dockerfile -- Playwright-ready
FROM python:3.11-slim

WORKDIR /app
COPY . /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system deps required by Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    curl \
    iproute2 \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps and Playwright
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

EXPOSE 443

# 1 worker with 32 threads:
# - Single worker is required because app state (users, sessions, tokens) is
#   stored in-memory dicts — multiple workers would have separate copies.
# - 32 threads gives enough headroom: each admin bot visit blocks a thread
#   for ~15-20s, but normal requests are instant. With ~40 players, worst case
#   is maybe 5-10 concurrent bot visits + normal traffic = well within 32.
# --timeout 120: don't kill the worker while bot threads are running
CMD ["gunicorn", \
     "--certfile=cert.pem", \
     "--keyfile=key.pem", \
     "--workers", "1", \
     "--threads", "32", \
     "--timeout", "120", \
     "-b", "0.0.0.0:443", \
     "app:app", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
