"""
Tests for the seed data loader.
Verifies that seed files are valid, properly structured,
and the loader functions work correctly.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Path to seed directory
SEED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed"

SEED_FILES = [
    "vat_regulations.json",
    "cit_regulations.json",
    "pit_regulations.json",
    "license_tax_regulations.json",
    "procedure_regulations.json",
]

REQUIRED_FIELDS = ["document_number", "title", "category", "content"]
VALID_CATEGORIES = {"vat", "cit", "pit", "license", "procedure", "penalty", "household"}


# ---------------------------------------------------------------------------
# Seed file validation tests
# ---------------------------------------------------------------------------

class TestSeedFileStructure:
    """Validate that all seed JSON files are properly structured."""

    def test_all_seed_files_exist(self):
        """All expected seed files must exist."""
        for filename in SEED_FILES:
            filepath = SEED_DIR / filename
            assert filepath.exists(), f"Missing seed file: {filename}"

    @pytest.mark.parametrize("filename", SEED_FILES)
    def test_seed_file_is_valid_json(self, filename: str):
        """Each seed file must contain valid JSON."""
        filepath = SEED_DIR / filename
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), f"{filename} must contain a JSON array"
        assert len(data) > 0, f"{filename} must not be empty"

    @pytest.mark.parametrize("filename", SEED_FILES)
    def test_seed_documents_have_required_fields(self, filename: str):
        """Each document in seed files must have required fields."""
        filepath = SEED_DIR / filename
        with open(filepath, encoding="utf-8") as f:
            docs = json.load(f)

        for i, doc in enumerate(docs):
            for field in REQUIRED_FIELDS:
                assert field in doc, (
                    f"{filename}[{i}] missing required field: {field}"
                )
                assert doc[field], (
                    f"{filename}[{i}] field '{field}' must not be empty"
                )

    @pytest.mark.parametrize("filename", SEED_FILES)
    def test_seed_documents_have_valid_category(self, filename: str):
        """Each document must have a valid category."""
        filepath = SEED_DIR / filename
        with open(filepath, encoding="utf-8") as f:
            docs = json.load(f)

        for i, doc in enumerate(docs):
            assert doc["category"] in VALID_CATEGORIES, (
                f"{filename}[{i}] has invalid category: {doc['category']}"
            )

    @pytest.mark.parametrize("filename", SEED_FILES)
    def test_seed_documents_have_valid_dates(self, filename: str):
        """effective_date must be valid YYYY-MM-DD format."""
        filepath = SEED_DIR / filename
        with open(filepath, encoding="utf-8") as f:
            docs = json.load(f)

        for i, doc in enumerate(docs):
            if "effective_date" in doc and doc["effective_date"]:
                try:
                    datetime.strptime(doc["effective_date"], "%Y-%m-%d")
                except ValueError:
                    pytest.fail(
                        f"{filename}[{i}] has invalid date: {doc['effective_date']}"
                    )

    def test_no_duplicate_document_numbers(self):
        """Document numbers must be unique across all seed files."""
        all_numbers = []
        for filename in SEED_FILES:
            filepath = SEED_DIR / filename
            with open(filepath, encoding="utf-8") as f:
                docs = json.load(f)
            all_numbers.extend(doc["document_number"] for doc in docs)

        assert len(all_numbers) == len(set(all_numbers)), (
            f"Duplicate document numbers found: "
            f"{[n for n in all_numbers if all_numbers.count(n) > 1]}"
        )

    def test_total_document_count(self):
        """Verify expected total number of seed documents."""
        total = 0
        for filename in SEED_FILES:
            filepath = SEED_DIR / filename
            with open(filepath, encoding="utf-8") as f:
                docs = json.load(f)
            total += len(docs)

        # 4 VAT + 3 CIT + 3 PIT + 2 License + 4 Procedure = 16
        assert total == 16, f"Expected 16 total documents, got {total}"


# ---------------------------------------------------------------------------
# Seed loader function tests
# ---------------------------------------------------------------------------

class TestSeedLoaderFunctions:
    """Test the seed loader utility functions."""

    def test_load_seed_files_returns_all_documents(self):
        """load_seed_files should return all documents from all files."""
        from data.seed_loader import load_seed_files
        docs = load_seed_files()
        assert len(docs) == 16

    def test_load_seed_files_all_have_document_number(self):
        """Every loaded document must have a document_number."""
        from data.seed_loader import load_seed_files
        docs = load_seed_files()
        for doc in docs:
            assert "document_number" in doc
            assert len(doc["document_number"]) > 0

    def test_load_seed_files_categories_covered(self):
        """All major tax categories should be represented."""
        from data.seed_loader import load_seed_files
        docs = load_seed_files()
        categories = {doc["category"] for doc in docs}
        assert "vat" in categories
        assert "cit" in categories
        assert "pit" in categories
        assert "license" in categories
        assert "procedure" in categories

    def test_load_seed_files_content_not_empty(self):
        """Every document must have non-trivial content."""
        from data.seed_loader import load_seed_files
        docs = load_seed_files()
        for doc in docs:
            assert len(doc["content"]) > 100, (
                f"Document {doc['document_number']} has too little content"
            )


class TestSeedVectorStore:
    """Test vector store seeding with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_seed_vector_store_indexes_all_docs(self):
        """seed_vector_store should call index_regulation for each document."""
        from data.seed_loader import load_seed_files

        mock_embedding = MagicMock()
        mock_embedding.get_document_count.return_value = 50

        mock_rag = MagicMock()
        mock_rag.index_regulation = AsyncMock()

        mock_llm = MagicMock()

        # Mock the classes at the module where they're defined
        mock_embedding_cls = MagicMock(return_value=mock_embedding)
        mock_llm_cls = MagicMock(return_value=mock_llm)
        mock_rag_cls = MagicMock(return_value=mock_rag)

        # Temporarily inject mock modules into sys.modules
        # so that lazy imports in seed_loader resolve to our mocks
        mock_embeddings_mod = MagicMock()
        mock_embeddings_mod.EmbeddingService = mock_embedding_cls

        mock_llm_mod = MagicMock()
        mock_llm_mod.LLMClient = mock_llm_cls

        mock_rag_mod = MagicMock()
        mock_rag_mod.RAGService = mock_rag_cls

        saved_modules = {}
        modules_to_mock = {
            "app.ai.embeddings": mock_embeddings_mod,
            "app.ai.llm_client": mock_llm_mod,
            "app.ai.rag_service": mock_rag_mod,
        }

        try:
            # Save and replace
            for mod_name, mock_mod in modules_to_mock.items():
                saved_modules[mod_name] = sys.modules.get(mod_name)
                sys.modules[mod_name] = mock_mod

            # Clear seed_loader so it re-imports
            if "data.seed_loader" in sys.modules:
                del sys.modules["data.seed_loader"]

            from data.seed_loader import seed_vector_store
            docs = load_seed_files()
            count = await seed_vector_store(docs)

            assert count == 16
            assert mock_rag.index_regulation.call_count == 16
        finally:
            # Restore original modules
            for mod_name, original in saved_modules.items():
                if original is None:
                    sys.modules.pop(mod_name, None)
                else:
                    sys.modules[mod_name] = original
            sys.modules.pop("data.seed_loader", None)

    @pytest.mark.asyncio
    async def test_seed_vector_store_passes_correct_metadata(self):
        """index_regulation should receive proper metadata."""
        mock_embedding = MagicMock()
        mock_embedding.get_document_count.return_value = 1

        mock_rag = MagicMock()
        mock_rag.index_regulation = AsyncMock()

        mock_embeddings_mod = MagicMock()
        mock_embeddings_mod.EmbeddingService = MagicMock(return_value=mock_embedding)
        mock_llm_mod = MagicMock()
        mock_rag_mod = MagicMock()
        mock_rag_mod.RAGService = MagicMock(return_value=mock_rag)

        test_doc = {
            "document_number": "TEST/2024",
            "title": "Test Document",
            "category": "vat",
            "content": "Test content here",
            "effective_date": "2024-01-01",
            "source_url": "https://example.com",
        }

        saved_modules = {}
        modules_to_mock = {
            "app.ai.embeddings": mock_embeddings_mod,
            "app.ai.llm_client": mock_llm_mod,
            "app.ai.rag_service": mock_rag_mod,
        }

        try:
            for mod_name, mock_mod in modules_to_mock.items():
                saved_modules[mod_name] = sys.modules.get(mod_name)
                sys.modules[mod_name] = mock_mod

            if "data.seed_loader" in sys.modules:
                del sys.modules["data.seed_loader"]

            from data.seed_loader import seed_vector_store
            await seed_vector_store([test_doc])

            call_kwargs = mock_rag.index_regulation.call_args
            assert call_kwargs.kwargs["doc_id"] == "TEST/2024"
            assert call_kwargs.kwargs["content"] == "Test content here"
            assert call_kwargs.kwargs["metadata"]["category"] == "vat"
            assert call_kwargs.kwargs["metadata"]["title"] == "Test Document"
        finally:
            for mod_name, original in saved_modules.items():
                if original is None:
                    sys.modules.pop(mod_name, None)
                else:
                    sys.modules[mod_name] = original
            sys.modules.pop("data.seed_loader", None)


class TestSeedDatabase:
    """Test database seeding with mocked SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_seed_database_inserts_all_docs(self):
        """seed_database should process all documents."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        mock_db_mod = MagicMock()
        mock_db_mod.engine = mock_engine
        mock_db_mod.async_session = MagicMock(return_value=mock_session)

        # We need the real Base and TaxRegulation for pg_insert to work
        # but importing them triggers the database module. Use a mock models module.
        mock_base = MagicMock()
        mock_base.metadata.create_all = MagicMock()

        mock_tax_reg = MagicMock()
        mock_tax_reg.__tablename__ = "tax_regulations"

        mock_models_mod = MagicMock()
        mock_models_mod.Base = mock_base
        mock_models_mod.TaxRegulation = mock_tax_reg

        test_docs = [
            {
                "document_number": "TEST/001",
                "title": "Test 1",
                "category": "vat",
                "content": "Content 1",
                "effective_date": "2024-01-01",
                "source_url": "https://example.com/1",
            },
            {
                "document_number": "TEST/002",
                "title": "Test 2",
                "category": "cit",
                "content": "Content 2",
                "effective_date": "2024-06-01",
            },
        ]

        # Also mock sqlalchemy if not installed
        mock_pg_insert = MagicMock()
        # pg_insert(...).values(...).on_conflict_do_update(...) chain
        mock_insert_obj = MagicMock()
        mock_pg_insert.return_value = mock_insert_obj
        mock_insert_obj.on_conflict_do_update.return_value = mock_insert_obj

        mock_sa_pg = MagicMock()
        mock_sa_pg.insert = mock_pg_insert

        saved_modules = {}
        modules_to_mock = {
            "app.db.database": mock_db_mod,
            "app.db.models": mock_models_mod,
        }

        # Only mock sqlalchemy if not available
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            mock_sa = MagicMock()
            mock_sa.dialects.postgresql = mock_sa_pg
            modules_to_mock.update({
                "sqlalchemy": mock_sa,
                "sqlalchemy.dialects": MagicMock(),
                "sqlalchemy.dialects.postgresql": mock_sa_pg,
            })

        try:
            for mod_name, mock_mod in modules_to_mock.items():
                saved_modules[mod_name] = sys.modules.get(mod_name)
                sys.modules[mod_name] = mock_mod

            if "data.seed_loader" in sys.modules:
                del sys.modules["data.seed_loader"]

            from data.seed_loader import seed_database
            count = await seed_database(test_docs)

            assert count == 2
            assert mock_session.execute.call_count == 2
            mock_session.commit.assert_awaited_once()
        finally:
            for mod_name, original in saved_modules.items():
                if original is None:
                    sys.modules.pop(mod_name, None)
                else:
                    sys.modules[mod_name] = original
            sys.modules.pop("data.seed_loader", None)

    @pytest.mark.asyncio
    async def test_seed_database_handles_missing_date(self):
        """Documents without effective_date should still be insertable."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        mock_db_mod = MagicMock()
        mock_db_mod.engine = mock_engine
        mock_db_mod.async_session = MagicMock(return_value=mock_session)

        mock_base = MagicMock()
        mock_base.metadata.create_all = MagicMock()

        mock_tax_reg = MagicMock()
        mock_tax_reg.__tablename__ = "tax_regulations"

        mock_models_mod = MagicMock()
        mock_models_mod.Base = mock_base
        mock_models_mod.TaxRegulation = mock_tax_reg

        test_docs = [
            {
                "document_number": "TEST/003",
                "title": "No Date Doc",
                "category": "procedure",
                "content": "Content without date",
            },
        ]

        mock_pg_insert = MagicMock()
        mock_insert_obj = MagicMock()
        mock_pg_insert.return_value = mock_insert_obj
        mock_insert_obj.on_conflict_do_update.return_value = mock_insert_obj

        mock_sa_pg = MagicMock()
        mock_sa_pg.insert = mock_pg_insert

        saved_modules = {}
        modules_to_mock = {
            "app.db.database": mock_db_mod,
            "app.db.models": mock_models_mod,
        }

        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            mock_sa = MagicMock()
            mock_sa.dialects.postgresql = mock_sa_pg
            modules_to_mock.update({
                "sqlalchemy": mock_sa,
                "sqlalchemy.dialects": MagicMock(),
                "sqlalchemy.dialects.postgresql": mock_sa_pg,
            })

        try:
            for mod_name, mock_mod in modules_to_mock.items():
                saved_modules[mod_name] = sys.modules.get(mod_name)
                sys.modules[mod_name] = mock_mod

            if "data.seed_loader" in sys.modules:
                del sys.modules["data.seed_loader"]

            from data.seed_loader import seed_database
            count = await seed_database(test_docs)

            assert count == 1
        finally:
            for mod_name, original in saved_modules.items():
                if original is None:
                    sys.modules.pop(mod_name, None)
                else:
                    sys.modules[mod_name] = original
            sys.modules.pop("data.seed_loader", None)
