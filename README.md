# Tax Assistant - Tro Ly Thue Ao

Virtual tax assistant for Vietnamese SMEs, households, and individual businesses. Supports tax consultation, calculation, and regulation lookup following Vietnamese tax law, integrated on Telegram and Zalo.

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  Telegram    │     │    Zalo     │
│    Bot       │     │     OA      │
└──────┬───────┘     └──────┬──────┘
       │    Webhooks        │
       ▼                    ▼
┌──────────────────────────────────┐
│      Node.js Gateway (TS)        │
│  ┌──────────┐  ┌──────────────┐  │
│  │ Channel  │  │   Session    │  │
│  │ Adapters │  │  Management  │  │
│  └──────────┘  └──────────────┘  │
│  ┌──────────┐  ┌──────────────┐  │
│  │  Rate    │  │   Message    │  │
│  │ Limiter  │  │   Router     │  │
│  └──────────┘  └──────────────┘  │
└───────────┬──────────────────────┘
            │  gRPC / REST
            ▼
┌──────────────────────────────────┐
│    Python Tax Engine (FastAPI)    │
│  ┌──────────┐  ┌──────────────┐  │
│  │   Tax    │  │   Intent     │  │
│  │  Rules   │  │ Classifier   │  │
│  └──────────┘  └──────────────┘  │
│  ┌──────────┐  ┌──────────────┐  │
│  │  AI/RAG  │  │  Vietnamese  │  │
│  │ Pipeline │  │     NLP      │  │
│  └──────────┘  └──────────────┘  │
│  ┌──────────┐  ┌──────────────┐  │
│  │ Document │  │    gRPC      │  │
│  │   OCR    │  │   Server     │  │
│  └──────────┘  └──────────────┘  │
└───────────┬──────────┬───────────┘
            │          │
     ┌──────▼──┐  ┌────▼────┐
     │PostgreSQL│  │  Redis  │
     │  + Chroma│  │         │
     └─────────┘  └─────────┘
```

## Features

**Tax Calculation** - VAT (GTGT), CIT (TNDN), PIT (TNCN), License Tax (Mon bai) with Vietnamese tax law rules

**Tax Consultation** - RAG-powered answers with legal references from 16 seeded regulation documents

**Multi-channel** - Telegram bot + Zalo Official Account with unified message format

**Vietnamese NLP** - Text normalization, money extraction, legal document reference parsing (via underthesea)

**Document Processing** - OCR for invoices/receipts with Tesseract Vietnamese

**Session Management** - Redis-backed conversation history with customer type tracking

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Gateway | Node.js 20+, TypeScript, Express |
| Tax Engine | Python 3.11+, FastAPI, SQLAlchemy |
| Communication | gRPC (internal), REST (external) |
| Database | PostgreSQL 16, Redis 7 |
| AI/RAG | Anthropic Claude, ChromaDB, sentence-transformers |
| NLP | underthesea (Vietnamese) |
| OCR | Tesseract (vie) |
| Messaging | Telegraf (Telegram), Zalo OA API |

## Project Structure

```
TaxAssistant/
├── proto/
│   └── tax_service.proto          # Shared gRPC contract
├── node-gateway/                  # Node.js I/O Gateway
│   └── src/
│       ├── channels/              # Telegram & Zalo adapters
│       ├── session/               # Redis session store
│       ├── middleware/             # Rate limiter, logging, errors
│       ├── grpc/                  # gRPC client to Python engine
│       ├── router/                # Message routing orchestrator
│       ├── api/routes/            # REST health & admin endpoints
│       └── index.ts               # Bootstrap & graceful shutdown
├── python-engine/                 # Python Tax Engine
│   ├── app/
│   │   ├── core/
│   │   │   ├── tax_rules/         # VAT, CIT, PIT, License Tax
│   │   │   ├── intent_classifier.py
│   │   │   └── tax_engine.py      # Central orchestrator
│   │   ├── ai/                    # LLM client, embeddings, RAG
│   │   ├── nlp/                   # Vietnamese NLP (underthesea)
│   │   ├── documents/             # OCR & data extraction
│   │   ├── db/                    # SQLAlchemy models & session
│   │   ├── api/routes/            # FastAPI REST endpoints
│   │   ├── grpc_server.py         # gRPC service implementation
│   │   └── main.py                # Dual server entry point
│   ├── data/
│   │   ├── seed/                  # 16 Vietnamese tax regulation JSONs
│   │   └── seed_loader.py         # DB + ChromaDB seed script
│   └── tests/                     # 203 unit tests
└── docker-compose.yml             # Full stack orchestration
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Anthropic API Key (for RAG/LLM features)
- Zalo OA credentials (optional)

### 1. Clone and configure

```bash
git clone <repository-url>
cd TaxAssistant

# Configure Node.js Gateway
cp node-gateway/.env.example node-gateway/.env
# Edit: TELEGRAM_BOT_TOKEN, ZALO_* credentials

# Configure Python Engine
cp python-engine/.env.example python-engine/.env
# Edit: ANTHROPIC_API_KEY
```

### 2. Start with Docker Compose

```bash
docker compose up -d
```

This starts 4 services:
- **gateway** - Node.js on port 3000 (REST) + 3001 (webhooks)
- **tax-engine** - Python on port 8000 (REST) + 50051 (gRPC)
- **postgres** - PostgreSQL 16 on port 5432
- **redis** - Redis 7 on port 6379

### 3. Seed tax regulations

```bash
docker compose exec tax-engine python -m data.seed_loader
```

Loads 16 Vietnamese tax regulation documents into PostgreSQL and ChromaDB.

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# Test tax calculation
curl -X POST http://localhost:8000/api/tax/message \
  -H "Content-Type: application/json" \
  -d '{"message": "tinh thue GTGT doanh thu 500 trieu", "customer_type": "sme"}'
```

## Local Development

### Python Engine

```bash
cd python-engine

# Install dependencies
pip install -r requirements.txt

# Run tests (no external services needed)
pytest tests/ -v

# Start server (requires PostgreSQL + Redis)
python -m app.main
```

### Node.js Gateway

```bash
cd node-gateway

# Install dependencies
npm install

# Development mode
npm run dev

# Build
npm run build
```

## Tax Rules Supported

| Tax | Vietnamese | Rate | Customer Types |
|-----|-----------|------|---------------|
| VAT | Thue GTGT | 10% (deduction) / 1-5% (direct) | SME, Household, Individual |
| CIT | Thue TNDN | 20% (enterprise) / 0.5-2% (household) | SME, Household, Individual |
| PIT | Thue TNCN | 5-35% progressive (7 brackets) | All |
| License | Mon bai | 2-3M (enterprise) / 0-1M (household) | SME, Household, Individual |

## Seed Data

16 regulation documents covering:

- **VAT** (4): Luat Thue GTGT, TT 219/2013, ND 123/2020, NQ 43/2022
- **CIT** (3): Luat Thue TNDN, TT 78/2014, TT 96/2015
- **PIT** (3): Luat Thue TNCN, TT 111/2013, NQ 954/2020
- **License Tax** (2): ND 139/2016, ND 22/2020
- **Procedures** (4): TT 80/2021, TT 40/2021, ND 125/2020, Luat QLT 38/2019

## Tests

```bash
cd python-engine
pytest tests/ -v
# 203 tests covering:
#   - Tax rules (VAT, CIT, PIT, License Tax)
#   - Intent classifier (12 intents, 4 categories)
#   - Tax Engine orchestration
#   - Seed data validation & loader
```

## API Endpoints

### Python Tax Engine (port 8000)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/tax/message` | Process tax query |
| POST | `/api/tax/calculate` | Direct tax calculation |
| GET | `/api/tax/info/{category}` | Tax category info |
| GET | `/api/tax/categories` | List all tax categories |

### Node.js Gateway (port 3000)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + Redis check |
| GET | `/admin/sessions/:id` | Get session details |
| DELETE | `/admin/sessions/:id` | Delete session |
| GET | `/admin/info` | Service info |

### gRPC (port 50051)

| RPC | Description |
|-----|-------------|
| `ProcessMessage` | Process tax query |
| `ProcessMessageStream` | Streaming response |
| `LookupRegulation` | RAG-powered regulation search |
| `ProcessDocument` | OCR document processing |

## License

Private - All rights reserved.
