"""
Tests for integrations module
"""

import pytest
from src.integrations.blacklist_whitelist import BlacklistWhitelist


@pytest.fixture
def config(tmp_path):
    """Test configuration"""
    return {
        "lists": {
            "blacklist_file": str(tmp_path / "blacklist.pkl"),
            "whitelist_file": str(tmp_path / "whitelist.pkl"),
            "auto_update": True,
        }
    }


@pytest.fixture
def bl_wl(config):
    """BlacklistWhitelist instance"""
    return BlacklistWhitelist(config)


def test_blacklist_whitelist_initialization(bl_wl):
    """Test BlacklistWhitelist initialization"""
    assert bl_wl is not None
    assert isinstance(bl_wl.blacklist, set)
    assert isinstance(bl_wl.whitelist, set)


def test_add_to_blacklist(bl_wl):
    """Test adding to blacklist"""
    email = "spam@example.com"
    result = bl_wl.add_to_blacklist(email)
    assert result is True
    assert bl_wl.is_blacklisted(email)


def test_add_to_whitelist(bl_wl):
    """Test adding to whitelist"""
    email = "trusted@example.com"
    result = bl_wl.add_to_whitelist(email)
    assert result is True
    assert bl_wl.is_whitelisted(email)


def test_blacklist_precedence(bl_wl):
    """Test that blacklist takes precedence"""
    email = "test@example.com"
    bl_wl.add_to_whitelist(email)
    bl_wl.add_to_blacklist(email)

    assert bl_wl.is_blacklisted(email)
    assert not bl_wl.is_whitelisted(email)


def test_domain_matching(bl_wl):
    """Test domain-based matching"""
    bl_wl.add_to_blacklist("example.com")

    assert bl_wl.is_blacklisted("user@example.com")
    assert bl_wl.is_blacklisted("another@example.com")


def test_export_import(bl_wl):
    """Test export and import"""
    bl_wl.add_to_blacklist("spam@example.com")
    bl_wl.add_to_whitelist("trusted@example.com")

    exported = bl_wl.export_to_dict()
    assert "blacklist" in exported
    assert "whitelist" in exported

    # Create new instance and import
    bl_wl2 = BlacklistWhitelist(bl_wl.config)
    bl_wl2.import_from_dict(exported)

    assert bl_wl2.is_blacklisted("spam@example.com")
    assert bl_wl2.is_whitelisted("trusted@example.com")
