# Production image for the FastAPI backend — slim (no PyTorch), binds to $PORT.
# Embeddings come from the HuggingFace API in deploy (set EMBEDDING_BACKEND=hf),
# so this image stays small enough for free tiers. Local dev still runs from the
# venv, not this image.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

# Railway / Render inject $PORT at runtime; default to 8000 for plain `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
