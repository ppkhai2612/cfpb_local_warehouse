import logging
from typing import Any
from datetime import datetime, timedelta
import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class CFPBClient:
    """Client for interacting with the CFPB Consumer Complaint Database API"""

    BASE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """Initialize the CFPB API client

        Params:
            timeout: Request timeout in seconds (default: 30)
        """
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration and headers
        
        Returns:
            Configured requests session
        """

        # Retry configuration
        retries = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[400, 404],
            allowed_methods=["GET"]
        )

        session = requests.Session()
        # Mount the HTTP adapter with retry configuration
        session.mount("https://www.consumerfinance.gov/", HTTPAdapter(max_retries=retries))
        # Set headers
        session.headers.update({
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
            "Upgrade-Insecure-Requests": "1"
        })

        # session.headers.update({
        #     "Accept": "application/json",
        #     "User-Agent": "Mozilla/5.0 (compatible; ConsumerComplaintETL/1.0; Python/requests"
        # })

        return session

    def get_complaints(
            self,
            date_received_min: str | None = None,
            date_received_max: str | None = None,
            sort: str = "created_date_asc",
            company: str | None = None,
            **filters
        ) -> list[dict[str, Any]]:
        """Fetch complaints from the CFPB API
        
        Params:
            date_received_max: Maximum date received (e.g., 2026-04-01)
            date_received_min: Minimum date received (e.g., 2026-04-01)
            sort: Used to sort records in a specific order (possible values are relevance_desc, relevance_asc, created_date_desc, created_date_asc)
            company: Name of the company to search for (e.g., Kriya Capital, LLC)
            **filters: Additional params used to filter (product, state,...)
        
        Returns:
            API response as dictionary

        Raises:
            requests.RequestException if the request fails
        """

        params = {
            "date_received_max": date_received_max,
            "date_received_min": date_received_min,
            "sort": sort
        }

        params.update(filters) # Update the filter parameters if they exist

        if company:
            params["company"] = company

        return self.get_complaints_pagination(params)

    def get_complaints_pagination(
            self,
            params: dict[str, Any],
            search_after: str | None = None,
            size: int | None = 10000
        ) -> list[dict[str, Any]]:
        """Fetch complaints with pagination support
        
        Params:
            params: Parameters are passed in by get_complaints
            search_after: Parameter for paginate results (combined with size)
            size: Parameter for paginate results (combined with search_after)

        Returns:
            list: list of complaints or an empty list
        """

        params["size"] = size
        all_complaints = []

        while True:
            try:
                
                if search_after:
                    params["search_after"] = search_after

                response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
                # print("STATUS:", response.status_code)
                # print("HEADERS:", response.headers.get("Content-Type"))
                # print("TEXT:", response.text[:500])
                # print(response.url)
                data = response.json()
                data = {k: data[k] for k in list(data)[1:]}

                hits = data.get("hits", {}).get("hits", [])
                complaints = [hit.get("_source", {}) for hit in hits]
                if not hits: # no records
                    break

                total_available_complaints = data.get("hits", {}).get("total", {}).get("value", 0)

                all_complaints.extend(complaints)

                # no more complaints to fetch
                if len(all_complaints) >= total_available_complaints:
                    logger.info("All complaints fetched")
                    break
                
                # update search_after that supports for pagination
                search_after_lst = hits[-1].get("sort", [])
                search_after_lst[0] = str(search_after_lst[0])
                search_after = "_".join(search_after_lst)

            except requests.RequestException as e:
                # error message and re-raise
                logger.error(f"Error when fetching complaints: {e}")
                raise

        logger.info(f"Total complaints fetched: {len(all_complaints)}")
        return all_complaints

    def close(self):
        """Close the CFPB API session"""
        if self.session:
            self.session.close()


if __name__ == "__main__":
    client = CFPBClient()
    complaints = client.get_complaints(
        date_received_min="2026-04-01",
        date_received_max="2026-04-01",
        company="Kriya Capital, LLC"
    )

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(complaints, f, indent=4, ensure_ascii=False)
    print(len(complaints))
    client.close()