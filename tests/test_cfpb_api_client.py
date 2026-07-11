"""Tests to verify that the CFPB API client is working as expected"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from cfpb.cfpb_client import CFPBClient


@pytest.fixture
def cfpb_client():
    """Fixture to return a CFPB API client"""
    return CFPBClient()


def test_cfpb_api_client_initialization(cfpb_client):
    """Test that the CFPB API client initializes correctly"""
    assert cfpb_client is not None
    assert cfpb_client.timeout == CFPBClient.DEFAULT_TIMEOUT
    assert cfpb_client.session is not None


def test_cfpb_api_client_initialization_with_custom_timeout():
    """Test that the CFPB API client initializes correctly with custom timeout"""
    client = CFPBClient(timeout=60)
    assert client.timeout == 60


def test_cfpb_api_client_can_fetch_data(cfpb_client):
    """Test that the CFPB client can fetch complaints"""
    generator = cfpb_client.get_complaints(
        date_received_min="2026-04-01",
        date_received_max="2026-04-02",
    )

    # first chunk
    first_chunk = next(generator)

    assert isinstance(first_chunk, list)
    assert len(first_chunk) > 0

    complaint = first_chunk[0]

    assert "product" in complaint
    assert "company" in complaint
    assert "issue" in complaint
    assert "complaint_id" in complaint

    assert complaint["product"] is not None
    assert complaint["company"] is not None


def test_cfpb_api_client_close(cfpb_client):
    """Test that the CFPB client can close its session"""
    assert cfpb_client.session is not None
    cfpb_client.close()
    assert True # if code reach this line, test success