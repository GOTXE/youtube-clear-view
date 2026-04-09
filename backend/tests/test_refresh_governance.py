"""Refresh governance unit tests."""

from app.services.refresh_governance import acquire_manual_refresh


def test_acquire_manual_refresh_blocks_second_request_for_same_user():
    with acquire_manual_refresh(user_id=1) as first:
        assert first["acquired"] is True
        with acquire_manual_refresh(user_id=1, channel_id=5) as second:
            assert second["acquired"] is False
            assert second["reason"] == "refresh_in_progress"
            assert second["active_scope"]["type"] == "all_channels"

    with acquire_manual_refresh(user_id=1, channel_id=5) as third:
        assert third["acquired"] is True
        assert third["scope"]["type"] == "channel"
