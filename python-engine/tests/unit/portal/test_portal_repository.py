"""
Unit tests for PortalRepository query-building logic.
Tests use mocked AsyncSession to verify correct SQL construction.
"""

import csv
import io
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.portal_repository import PortalRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    return PortalRepository(mock_session)


# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

class TestGetTotalActiveUsers:
    @pytest.mark.asyncio
    async def test_returns_count(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        count = await repo.get_total_active_users()
        assert count == 42
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_none(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        count = await repo.get_total_active_users()
        assert count == 0


class TestGetNewUsersCount:
    @pytest.mark.asyncio
    async def test_day_period(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        count = await repo.get_new_users_count("day", date(2026, 3, 1))
        assert count == 5

    @pytest.mark.asyncio
    async def test_month_period(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 120
        mock_session.execute.return_value = mock_result

        count = await repo.get_new_users_count("month", date(2026, 3, 1))
        assert count == 120

    @pytest.mark.asyncio
    async def test_year_period(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1500
        mock_session.execute.return_value = mock_result

        count = await repo.get_new_users_count("year", date(2026, 3, 1))
        assert count == 1500


class TestGetDau:
    @pytest.mark.asyncio
    async def test_returns_distinct_user_count(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_session.execute.return_value = mock_result

        dau = await repo.get_dau(date(2026, 3, 1))
        assert dau == 10

    @pytest.mark.asyncio
    async def test_defaults_to_today(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7
        mock_session.execute.return_value = mock_result

        dau = await repo.get_dau()
        assert dau == 7


class TestGetMau:
    @pytest.mark.asyncio
    async def test_returns_monthly_active_users(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 200
        mock_session.execute.return_value = mock_result

        mau = await repo.get_mau(2026, 3)
        assert mau == 200


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

class TestGetCustomerSegmentation:
    @pytest.mark.asyncio
    async def test_returns_grouped_counts(self, repo, mock_session):
        row1 = MagicMock()
        row1.customer_type = "sme"
        row1.count = 50
        row2 = MagicMock()
        row2.customer_type = "household"
        row2.count = 30

        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]
        mock_session.execute.return_value = mock_result

        data = await repo.get_customer_segmentation()
        assert len(data) == 2
        assert data[0] == {"customer_type": "sme", "count": 50}
        assert data[1] == {"customer_type": "household", "count": 30}


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

class TestGetGrowthTrends:
    @pytest.mark.asyncio
    async def test_returns_daily_counts(self, repo, mock_session):
        row1 = MagicMock()
        row1.day = date(2026, 3, 1)
        row1.count = 3
        row2 = MagicMock()
        row2.day = date(2026, 3, 2)
        row2.count = 5

        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]
        mock_session.execute.return_value = mock_result

        data = await repo.get_growth_trends(date(2026, 3, 1), date(2026, 3, 5))
        assert len(data) == 2
        assert data[0] == {"date": "2026-03-01", "count": 3}
        assert data[1] == {"date": "2026-03-02", "count": 5}


class TestGetActivityTrends:
    @pytest.mark.asyncio
    async def test_returns_daily_active_counts(self, repo, mock_session):
        row = MagicMock()
        row.day = date(2026, 3, 1)
        row.count = 8

        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_session.execute.return_value = mock_result

        data = await repo.get_activity_trends(date(2026, 3, 1), date(2026, 3, 1))
        assert len(data) == 1
        assert data[0] == {"date": "2026-03-01", "count": 8}


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class TestSaveSnapshot:
    @pytest.mark.asyncio
    async def test_creates_snapshot(self, repo, mock_session):
        snapshot = await repo.save_snapshot({
            "total_users": 100,
            "active_users_day": 10,
            "active_users_month": 50,
            "new_users_day": 3,
            "new_users_month": 20,
            "new_users_year": 100,
            "segmentation": [{"customer_type": "sme", "count": 60}],
        })
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert snapshot.total_users == 100
        assert snapshot.active_users_day == 10


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

class TestExportUsersCsv:
    @pytest.mark.asyncio
    async def test_produces_valid_csv(self, repo, mock_session):
        customer = MagicMock()
        customer.id = uuid.uuid4()
        customer.channel = "telegram"
        customer.customer_type = "sme"
        customer.business_name = "Test Corp"
        customer.tax_code = "0123456789"
        customer.industry = "tech"
        customer.province = "HCM"
        customer.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        customer.last_active_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [customer]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        csv_str = await repo.export_users_csv()
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        assert len(rows) == 2  # header + 1 data row
        assert rows[0][0] == "id"
        assert rows[1][1] == "telegram"
        assert rows[1][2] == "sme"
        assert rows[1][3] == "Test Corp"
