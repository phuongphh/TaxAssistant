"""
Unit tests for portal metrics scheduler.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portal.scheduler import compute_and_store_snapshot


class TestComputeAndStoreSnapshot:
    @pytest.mark.asyncio
    @patch("app.portal.scheduler.async_session")
    async def test_computes_all_metrics_and_saves(self, mock_session_factory):
        """Verify that the scheduler computes all metric types and saves a snapshot."""
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock all the repository method return values
        mock_result_scalar = MagicMock()
        mock_result_scalar.scalar.return_value = 100
        mock_session.execute.return_value = mock_result_scalar

        # Mock the segmentation result
        seg_row = MagicMock()
        seg_row.customer_type = "sme"
        seg_row.count = 60
        seg_result = MagicMock()
        seg_result.all.return_value = [seg_row]

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # The 7th call is the segmentation query (group_by)
            if call_count == 7:
                return seg_result
            return mock_result_scalar

        mock_session.execute = mock_execute
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        await compute_and_store_snapshot()

        # Verify a snapshot was added and committed
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify the snapshot has expected fields
        snapshot = mock_session.add.call_args[0][0]
        assert snapshot.total_users == 100
        assert snapshot.active_users_day == 100
        assert snapshot.active_users_month == 100

    @pytest.mark.asyncio
    @patch("app.portal.scheduler.async_session")
    async def test_handles_empty_database(self, mock_session_factory):
        """When the database has no data, snapshot should be saved with zeros."""
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result_scalar = MagicMock()
        mock_result_scalar.scalar.return_value = 0

        mock_seg_result = MagicMock()
        mock_seg_result.all.return_value = []

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 7:
                return mock_seg_result
            return mock_result_scalar

        mock_session.execute = mock_execute
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        await compute_and_store_snapshot()

        snapshot = mock_session.add.call_args[0][0]
        assert snapshot.total_users == 0
        assert snapshot.new_users_day == 0
