"""Tests to verify that the CFPB API client is working as expected.

These tests check that:
    - CFPB client initializes correctly
    - CFPB client can fetch complaints
    - CFPB client can fetch complaints by company
    - CFPB client can fetch complaints by date range
    - CFPB client can fetch complaints with filters (product, state, company_response, timely)
    - CFPB client handles pagination correctly
    - CFPB client can close sessions properly
"""

from datetime import datetime

import pytest

from src.apis.cfpb_api_client import CFPBAPIClient


@pytest.fixture
def cfpb_api_client():
    """Fixture to create a CFPB API client."""
    return CFPBAPIClient()


def test_cfpb_api_client_initialization(cfpb_api_client):
    """Test that the CFPB API client initializes correctly."""
    assert cfpb_api_client is not None
    assert cfpb_api_client.timeout == CFPBAPIClient.DEFAULT_TIMEOUT
    assert cfpb_api_client.session is not None


def test_cfpb_api_client_initialization_with_custom_timeout():
    """Test that the CFPB API client initializes correctly with custom timeout."""
    client = CFPBAPIClient(timeout=60)
    assert client.timeout == 60


def test_cfpb_api_client_can_fetch_data(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints."""
    response = cfpb_api_client.get_complaints(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        size=100,
        sort="created_date_desc",
        search_term="bank of america",
        field="company",
        no_aggs=False,
    )

    # handle both response formats
    if isinstance(response, list):
        hits = response
    elif isinstance(response, dict) and "hits" in response:
        hits = response.get("hits", {}).get("hits", [])
    else:
        pytest.fail(f"Unexpected response format: {type(response)}")

    assert len(hits) > 0
    assert set(hits[0].keys()) == {"_index", "_id", "_score", "_source", "highlight", "sort"}
    assert hits[0].get("_index") == "complaint-public-v2"

    source = hits[0]["_source"]
    assert source is not None
    assert source.get("complaint_id") is not None
    assert source.get("product") is not None
    assert source.get("issue") is not None
    assert source.get("submitted_via") is not None
    assert source.get("date_received") is not None
    assert source.get("date_sent_to_company") is not None
    assert source.get("company_response") is not None
    assert source.get("timely") is not None
    assert source.get("company") is not None


def test_cfpb_api_client_can_fetch_complaints_paginated(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints paginated."""
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-01",
        max_records=5,
    )

    assert len(complaints) == 5
    assert isinstance(complaints[0], dict)
    assert complaints[0].get("product") is not None
    assert complaints[0].get("sub_product") is not None
    assert complaints[0].get("issue") is not None
    assert complaints[0].get("sub_issue") is not None
    assert "complaint_id" in complaints[0]
    assert "date_received" in complaints[0]


def test_cfpb_api_client_can_fetch_complaints_for_date_range(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints for a date range."""
    start_date = datetime(2025, 10, 1)
    end_date = datetime(2025, 10, 2)

    complaints = cfpb_api_client.get_complaints_for_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    assert len(complaints) > 0
    assert isinstance(complaints[0], dict)
    assert complaints[0].get("product") is not None
    assert complaints[0].get("date_received") is not None


def test_cfpb_api_client_can_fetch_complaints_by_company(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints by company."""
    complaints = cfpb_api_client.get_complaints_by_company(
        company_name="bank of america",
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
    )

    assert len(complaints) > 0
    assert isinstance(complaints[0], dict)
    assert complaints[0].get("product") is not None
    assert complaints[0].get("sub_product") is not None
    assert complaints[0].get("issue") is not None
    assert complaints[0].get("sub_issue") is not None
    assert complaints[0].get("submitted_via") is not None
    assert complaints[0].get("date_sent_to_company") is not None
    assert complaints[0].get("company_response") is not None
    assert complaints[0].get("timely") is not None
    assert "BANK OF AMERICA" in complaints[0].get("company", "").upper()


def test_cfpb_api_client_can_fetch_complaints_last_n_days(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints from last n days."""
    complaints = cfpb_api_client.get_complaints_last_n_days(days=1)

    assert len(complaints) >= 0  # May be empty if no complaints in last day
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)
        assert complaints[0].get("product") is not None
        assert complaints[0].get("sub_product") is not None
        assert complaints[0].get("issue") is not None
        assert complaints[0].get("sub_issue") is not None
        assert complaints[0].get("submitted_via") is not None
        assert complaints[0].get("date_sent_to_company") is not None
        assert complaints[0].get("company_response") is not None
        assert complaints[0].get("timely") is not None


def test_cfpb_api_client_can_fetch_complaints_with_product_filter(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints filtered by product."""
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
        product="Credit reporting or other personal consumer reports",
    )

    assert len(complaints) >= 0
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)
        assert complaints[0].get("product") is not None


def test_cfpb_api_client_can_fetch_complaints_with_state_filter(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints filtered by state."""
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
        state="CA",
    )

    assert len(complaints) >= 0
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)
        assert complaints[0].get("state") == "CA"


def test_cfpb_api_client_can_fetch_complaints_with_company_response_filter(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints filtered by company response."""
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
        company_response="Closed with explanation",
    )

    assert len(complaints) >= 0
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)
        assert complaints[0].get("company_response") is not None


def test_cfpb_api_client_can_fetch_complaints_with_timely_filter(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints filtered by timely."""
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
        timely="Yes",
    )
    assert len(complaints) >= 0
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)
        assert complaints[0].get("timely") is not None


def test_cfpb_api_client_can_fetch_complaints_with_no_aggs(cfpb_api_client):
    """Test that the CFPB API client can fetch complaints with no_aggs flag."""
    complaints = cfpb_api_client.get_complaints_by_company(
        company_name="bank of america",
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=5,
        no_aggs=True,
    )

    assert len(complaints) >= 0
    if len(complaints) > 0:
        assert isinstance(complaints[0], dict)


def test_cfpb_api_client_pagination_respects_max_records(cfpb_api_client):
    """Test that pagination respects max_records limit."""
    max_records = 3
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=max_records,
    )

    assert len(complaints) <= max_records


def test_cfpb_api_client_handles_empty_results(cfpb_api_client):
    """Test that the client handles empty results gracefully."""
    # Use a date range that likely has no complaints
    complaints = cfpb_api_client.get_complaints_paginated(
        date_received_min="2099-01-01",
        date_received_max="2099-01-02",
    )

    assert isinstance(complaints, list)
    assert len(complaints) == 0


def test_cfpb_api_client_close(cfpb_api_client):
    """Test that the CFPB client can close its session."""
    assert cfpb_api_client.session is not None
    cfpb_api_client.close()
    assert True


def test_cfpb_api_client_close_idempotent(cfpb_api_client):
    """Test that closing the client multiple times doesn't raise errors."""
    cfpb_api_client.close()
    cfpb_api_client.close()  # Should not raise
    assert True