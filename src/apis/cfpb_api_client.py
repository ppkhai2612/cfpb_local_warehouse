"""CFPB Consumer Complaint Database API Client

This module provides a client for interacting with the Consumer Financial
Protection Bureau's Consumer Complaint Database API.

API Documentation: https://cfpb.github.io/api/ccdb/api.html
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)


class CFPBAPIClient:
    """Client for interacting with the CFPB Consumer Complaint Database API"""

    BASE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """Initialize the CFPB API client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic and proper headers.

        Returns:
            Configured requests session
        """
        session = requests.Session()

        # CRITICAL: Add User-Agent header (CFPB API requires this to avoid 403 errors)
        session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en,fr-FR;q=0.9,fr;q=0.8,en-US;q=0.7,vi;q=0.6,zh-CN;q=0.5,zh;q=0.4",
                "Cache-Control": "max-age=0",
                "Cookie": "csrftoken=5UfhGNcBGAqeLxBvPquQjr8NpIDk1BSV; _gid=GA1.2.1666023361.1777088439; _ga_CSLL4ZEK4L=GS2.1.s1777088440$o77$g1$t1777088448$j52$l0$h0; _ga=GA1.2.65263089.1774325663; _ga_CMRC03R7CT=GS2.1.s1777088439$o78$g1$t1777088448$j51$l0$h0",
                "If-None-Match": '"e221081a0c480267174853427fb150df"',
                "Priority": "u=0, i",
                "Sec-Ch-Ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                "Sec-Ch-Ua-Platform": '"Linux"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Retry configuration
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def get_complaints(
        self,
        date_received_min: str | None = None,
        date_received_max: str | None = None,
        size: int = 10000,
        frm: int = 0,
        sort: str = "created_date_desc",
        search_term: str | None = None,
        field: str | None = None,
        no_aggs: bool = False,
        **filters,
    ) -> dict[str, Any]:
        """Fetch consumer complaints from the CFPB API.

        Args:
            date_received_min: Minimum date received (YYYY-MM-DD)
            date_received_max: Maximum date received (YYYY-MM-DD)
            size: Number of records to return (max 10000)
            frm: Starting index for pagination
            sort: Sort order for results
            search_term: Search term to filter results (e.g., company name)
            field: Field to search in (e.g., 'company')
            no_aggs: Disable aggregations for faster responses
            **filters: Additional filter parameters (product, company, state, etc.)

        Returns:
            API response as dictionary

        Raises:
            requests.RequestException if API request fails
        """
        params = {
            "size": min(size, 10000),  # API limit is 10000
            "frm": frm,
            "sort": sort,
            # "format": "json"
        }

        # Add date filters
        if date_received_min:
            params["date_received_min"] = date_received_min
        if date_received_max:
            params["date_received_max"] = date_received_max

        # Add search parameters
        if search_term:
            params["search_term"] = search_term
        if field:
            params["field"] = field

        # Add no_aggs flag
        if no_aggs:
            params["no_aggs"] = "true"

        # Add additional filters
        params.update(filters)

        # params = urlencode(params, quote_via=quote)

        try:
            logger.info(f"Fetching complaints from CFPB API with params: {params}")
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # Handle different response formats
            if isinstance(data, list):
                # Direct list format
                logger.info(f"Successfully fetched {len(data)} complaints (direct list format)")
            elif isinstance(data, dict) and "hits" in data:
                # Nested dict format
                hits = data.get("hits", {}).get("hits", [])
                total_value = data.get("hits", {}).get("total", {})
                if isinstance(total_value, dict):
                    total = total_value.get("value", 0)
                else:
                    total = total_value
                logger.info(
                    f"Successfully fetched {len(hits)} complaints. Total available: {total}"
                )
            else:
                logger.warning(f"Unexpected response format: {type(data)}")

            return data

        except requests.RequestException as e:
            logger.error(f"Error when fetching complaints from CFPB API: {e}")
            raise

    def get_complaints_paginated(
        self,
        date_received_min: str | None = None,
        date_received_max: str | None = None,
        max_records: int | None = None,
        **filters,
    ) -> list[dict[str, Any]]:
        """Fetch all complaints with pagination support.

        Args:
            date_received_min: Minimum received date (YYYY-MM-DD)
            date_received_max: Maximum received date (YYYY-MM-DD)
            max_records: Maximum total records to fetch (None for all)
            **filters: Additional filter parameters

        Returns:
            List of complaint records
        """
        all_complaints = []
        page_size = 10000
        search_after = None

        while True:
            # Check if we've reached max_records
            if max_records and len(all_complaints) >= max_records:
                logger.info(f"Reached max_records limit: {max_records}")
                break

            # Fetch page
            response = self.get_complaints(
                date_received_min=date_received_min,
                date_received_max=date_received_max,
                size=page_size,
                search_after=search_after,
                **filters,
            )

            # Handle different response formats
            if isinstance(response, list):
                # Direct list format
                hits = response
                complaints = [hit.get("_source", {}) for hit in hits]
                total_available = len(hits)
            elif isinstance(response, dict) and "hits" in response:
                # Nested dict format
                hits = response.get("hits", {}).get("hits", [])
                complaints = [hit.get("_source", {}) for hit in hits]
                total_value = response.get("hits", {}).get("total", {})
                if isinstance(total_value, dict):
                    total_available = total_value.get("value", 0)
                else:
                    total_available = total_value
            else:
                logger.warning("Unexpected response format")
                break

            if not hits:
                logger.info("No more complaints to fetch")
                break

            all_complaints.extend(complaints)
            logger.info(
                f"Fetched {len(complaints)} complaints. Total so far: {len(all_complaints)}"
            )

            # Check if we're exceeded max_records and truncate if needed
            if max_records and len(all_complaints) > max_records:
                all_complaints = all_complaints[:max_records]
                logger.info(f"Truncated to max_records limit: {max_records}")
                break

            # Check if there are more results
            if len(all_complaints) >= total_available:
                logger.info("Fetched all available complaints")
                break

            # Move to next call
            search_after_lst = hits[-1].get("sort", [])
            search_after_lst[0] = str(search_after_lst[0])
            search_after = "_".join(search_after_lst)

        logger.info(f"Total complaints fetched: {len(all_complaints)}")
        return all_complaints

    def get_complaints_by_company(
        self,
        company_name: str | None = None,
        date_received_min: str | None = None,
        date_received_max: str | None = None,
        max_records: int | None = None,
        no_aggs: bool = True,
        **filters,
    ) -> list[dict[str, Any]]:
        """Fetch complaints for a specific company

        Args:
            company_name: Name of the company to search for (e.g., 'jpmorgan')
            date_received_min: Minimum date received (YYYY-MM-DD)
            date_received_max: Maximum date received (YYYY-MM-DD)
            max_records: Maximum total records to fetch (None for all)
            no_aggs: Disable aggregations for faster responses (default: True)
            **filters: Additional filter parameters

        Returns:
            List of complaint records for the specified company
        """
        logger.info(f"Fetching complaints for company: {company_name}")

        return self.get_complaints_paginated(
            date_received_min=date_received_min,
            date_received_max=date_received_max,
            max_records=max_records,
            search_term=company_name,
            field="company",
            no_aggs=no_aggs,
            **filters,
        )

    def get_complaints_for_date_range(
        self, start_date: datetime, end_date: datetime, **filters
    ) -> list[dict[str, Any]]:
        """Fetch complaints for a specific date range.

        Args:
            start_date: Start date for complaints
            end_date: End date for complaints
            **filters: Additional filter parameters

        Returns:
            List of complaint records
        """
        date_min = start_date.strftime("%Y-%m-%d")
        date_max = end_date.strftime("%Y-%m-%d")

        logger.info(f"Fetching complaints from {date_min} to {date_max}")

        return self.get_complaints_paginated(
            date_received_min=date_min, date_received_max=date_max, **filters
        )

    def get_complaints_last_n_days(self, days: int = 1, **filters) -> list[dict[str, Any]]:
        """Fetch complaints from the last N days.

        Args:
            days: Number of days to look back
            **filters: Additional filter parameters

        Returns:
            List of complaint records
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        return self.get_complaints_for_date_range(
            start_date=start_date, end_date=end_date, **filters
        )

    def close(self):
        """Close the API client session."""
        if self.session:
            self.session.close()
            logger.info("CFPB API client session closed")


if __name__ == "__main__":
    start_time = time.time()
    client = CFPBAPIClient()
    # response = client.get_complaints(
    #     date_received_min="2011-12-01",
    #     date_received_max="2025-10-02",
    #     size=100,
    #     sort="created_date_desc",
    #     search_term="bank of america",
    #     field="company",
    #     no_aggs=False
    # )
    # end_time = time.time()
    # print(f"Time taken: {end_time - start_time} seconds")

    # hits = response.get("hits", {}).get("hits", [])
    # complaints = [hit.get("_source", {}) for hit in hits]
    # print(complaints[0])

    complaints = client.get_complaints_by_company(
        company_name="bank of america",
        date_received_min="2025-10-01",
        date_received_max="2025-10-02",
        max_records=10,
    )
    print(complaints[1])
