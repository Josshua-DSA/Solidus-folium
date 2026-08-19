"""
Tests for shared/utils/user_profile.py — User Profile Manager.
"""
import os
import tempfile
import pytest
from shared.utils.user_profile import ProfileManager, UserProfile, StockPosition


def test_stock_position_properties():
    pos = StockPosition(ticker="BBCA.JK", lots=10, avg_price=9000.0)
    assert pos.shares == 1000
    assert pos.total_value == 9_000_000.0


def test_user_profile_serialization():
    pos = StockPosition(ticker="TLKM.JK", lots=5, avg_price=3800.0)
    prof = UserProfile(
        investor_name="Test Investor",
        rdn_balance=25_000_000.0,
        positions=[pos],
    )

    d = prof.to_dict()
    assert d["investor_name"] == "Test Investor"
    assert d["rdn_balance"] == 25_000_000.0
    assert len(d["positions"]) == 1

    loaded = UserProfile.from_dict(d)
    assert loaded.investor_name == "Test Investor"
    assert loaded.rdn_balance == 25_000_000.0
    assert loaded.positions[0].ticker == "TLKM.JK"
    assert loaded.positions[0].shares == 500


def test_profile_manager_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "user_profile.json")
        pm = ProfileManager(profile_path=file_path)

        assert not pm.exists()

        default_prof = pm.load()
        assert default_prof.rdn_balance == 10_000_000.0

        custom_prof = UserProfile(
            investor_name="Trader Pro",
            rdn_balance=50_000_000.0,
            positions=[StockPosition(ticker="BMRI.JK", lots=20, avg_price=6500.0)],
        )
        pm.save(custom_prof)

        assert pm.exists()
        reloaded = pm.load()
        assert reloaded.rdn_balance == 50_000_000.0
        assert reloaded.positions[0].ticker == "BMRI.JK"
        assert reloaded.updated_at != ""
