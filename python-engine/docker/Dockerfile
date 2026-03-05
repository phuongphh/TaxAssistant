FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel maturin cython

COPY python-engine/requirements.txt .
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# --- Production stage ---
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for OCR & PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN useradd -m -u 1001 appuser

# Copy new structure
COPY python-engine/core/ ./core/
COPY python-engine/services/ ./services/
COPY python-engine/db/ ./db/
COPY python-engine/documents/ ./documents/
COPY python-engine/nlp/ ./nlp/
COPY python-engine/api/ ./api/
COPY python-engine/main.py ./main.py
COPY python-engine/config.py ./config.py
COPY python-engine/grpc_server.py ./grpc_server.py
COPY python-engine/data/ ./data/
COPY proto/ /proto/

RUN mkdir -p /app/data/chroma && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000 50051

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
