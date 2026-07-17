FROM python:3.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV FLAG="BHCTF{eml_tr33s_4r3_fuN}"

EXPOSE 1337

# Unbuffered so container logs show the "listening" line immediately.
CMD ["python", "-u", "server.py"]
