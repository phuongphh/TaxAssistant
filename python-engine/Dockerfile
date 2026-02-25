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

RUN pip install --no-cache-dir --upgrade pip setuptools wheel maturin

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

COPY python-engine/app/ ./app/
COPY proto/ /proto/

USER appuser

EXPOSE 8000 50051

CMD ["python", "-m", "app.main"]
