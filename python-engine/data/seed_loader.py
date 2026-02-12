"""
Seed loader script for Vietnamese tax regulation data.

Loads JSON seed files into:
1. PostgreSQL (tax_regulations table) - for structured queries and admin
2. ChromaDB vector store - for RAG retrieval

Usage:
    python -m data.seed_loader          # Load all seed files
    python -m data.seed_loader --dry-run  # Preview without writing
    python -m data.seed_loader --vector-only  # Only index into ChromaDB
    python -m data.seed_loader --db-only     # Only insert into PostgreSQL
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_loader")

SEED_DIR = Path(__file__).resolve().parent / "seed"

SEED_FILES = [
    "vat_regulations.json",
    "cit_regulations.json",
    "pit_regulations.json",
    "license_tax_regulations.json",
    "procedure_regulations.json",
]


def load_seed_files() -> list[dict]:
    """Read all JSON seed files and return a flat list of regulation documents."""
    all_docs = []
    for filename in SEED_FILES:
        filepath = SEED_DIR / filename
        if not filepath.exists():
            logger.warning("Seed file not found: %s", filepath)
            continue

        with open(filepath, encoding="utf-8") as f:
            docs = json.load(f)
            logger.info("Loaded %d documents from %s", len(docs), filename)
            all_docs.extend(docs)

    return all_docs


async def seed_database(documents: list[dict]) -> int:
    """Insert or update regulation documents in PostgreSQL."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.database import async_session, engine
    from app.db.models import Base, TaxRegulation

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    inserted = 0
    async with async_session() as session:
        for doc in documents:
            effective_date = None
            if doc.get("effective_date"):
                effective_date = datetime.strptime(
                    doc["effective_date"], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)

            stmt = pg_insert(TaxRegulation).values(
                document_number=doc["document_number"],
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                effective_date=effective_date,
                source_url=doc.get("source_url"),
            )
            # Upsert: on conflict update content and title
            stmt = stmt.on_conflict_do_update(
                index_elements=["document_number"],
                set_={
                    "title": stmt.excluded.title,
                    "content": stmt.excluded.content,
                    "category": stmt.excluded.category,
                    "effective_date": stmt.excluded.effective_date,
                    "source_url": stmt.excluded.source_url,
                },
            )
            await session.execute(stmt)
            inserted += 1

        await session.commit()

    logger.info("Database: upserted %d regulation documents", inserted)
    return inserted


async def seed_vector_store(documents: list[dict]) -> int:
    """Index regulation documents into ChromaDB for RAG retrieval."""
    from app.ai.embeddings import EmbeddingService
    from app.ai.llm_client import LLMClient
    from app.ai.rag_service import RAGService

    embedding_service = EmbeddingService()
    llm_client = LLMClient()
    rag_service = RAGService(embedding_service, llm_client)

    indexed = 0
    for doc in documents:
        metadata = {
            "document_number": doc["document_number"],
            "title": doc["title"],
            "category": doc["category"],
            "effective_date": doc.get("effective_date", ""),
            "source_url": doc.get("source_url", ""),
        }

        await rag_service.index_regulation(
            doc_id=doc["document_number"],
            content=doc["content"],
            metadata=metadata,
        )
        indexed += 1

    total_chunks = embedding_service.get_document_count()
    logger.info(
        "Vector store: indexed %d documents (%d total chunks)",
        indexed,
        total_chunks,
    )
    return indexed


def print_summary(documents: list[dict]) -> None:
    """Print a summary of documents by category."""
    categories: dict[str, list] = {}
    for doc in documents:
        cat = doc["category"]
        categories.setdefault(cat, []).append(doc)

    print("\n" + "=" * 60)
    print("SEED DATA SUMMARY")
    print("=" * 60)
    print(f"Total documents: {len(documents)}")
    print()
    for cat, docs in sorted(categories.items()):
        print(f"  [{cat.upper()}] ({len(docs)} documents):")
        for d in docs:
            print(f"    - {d['document_number']}: {d['title'][:60]}...")
    print("=" * 60 + "\n")


async def verify_database() -> int:
    """Verify documents were inserted into the database."""
    from sqlalchemy import select

    from app.db.database import async_session
    from app.db.models import TaxRegulation

    async with async_session() as session:
        result = await session.execute(
            select(TaxRegulation.document_number, TaxRegulation.category)
        )
        rows = result.all()
        logger.info("Database verification: %d regulations found", len(rows))
        return len(rows)


async def main() -> None:
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args
    vector_only = "--vector-only" in args
    db_only = "--db-only" in args

    logger.info("Starting seed loader...")
    documents = load_seed_files()

    if not documents:
        logger.error("No seed documents found. Exiting.")
        sys.exit(1)

    print_summary(documents)

    if dry_run:
        logger.info("Dry run mode - no data written.")
        return

    # Seed PostgreSQL
    if not vector_only:
        try:
            db_count = await seed_database(documents)
            verify_count = await verify_database()
            logger.info(
                "PostgreSQL: %d upserted, %d verified", db_count, verify_count
            )
        except Exception:
            logger.exception("Failed to seed PostgreSQL database")
            if not db_only:
                logger.info("Continuing with vector store indexing...")

    # Seed ChromaDB
    if not db_only:
        try:
            vec_count = await seed_vector_store(documents)
            logger.info("ChromaDB: %d documents indexed", vec_count)
        except Exception:
            logger.exception("Failed to seed ChromaDB vector store")

    logger.info("Seed loading complete!")


if __name__ == "__main__":
    asyncio.run(main())
