FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so they cache across rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py index.html ./
COPY static ./static
# The flag image, kept out of the public /static mount.
COPY secret ./secret

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]