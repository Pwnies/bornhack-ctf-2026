FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV DATABASE=/app/data/challenge.db
ENV FLAG=ctf{draw_your_way_in}
ENV SECRET_KEY=change-me-for-production

EXPOSE 5000

CMD ["python", "app.py"]
