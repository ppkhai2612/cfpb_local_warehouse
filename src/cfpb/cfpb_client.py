"""Consumer Complaint Database API Client

This script implements a CFPBClient interface for interacting CFPB API
API docs: https://cfpb.github.io/api/ccdb/api.html
"""

import logging
from typing import Any
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

        Args:
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
            company: str | None = None,
            sort: str = "created_date_desc",
            no_aggs: bool = True
        ) -> list[dict[str, Any]]:
        """Fetch complaints from the CFPB API
        
        Args:
            date_received_min (str | None): Minimum date received (YYYY-MM-DD)
            date_received_max (str | None): Maximum date received (YYYY-MM-DD)
            company (str | None): Company name to fetch (e.g., Kriya Capital, LLC)
            sort (str): Sort order for results
                Possible values are relevance_desc, relevance_asc, created_date_desc, created_date_asc
                Default to created_date_desc
            no_aggs (bool): Disable aggregations in result. Default to True
        
        Returns:
            list: list of complaints or an empty list if no records were found

        Raises:
            requests.RequestException if the request fails
        """
        # update parameters
        params = {
            "date_received_min": date_received_min,
            "date_received_max": date_received_max,
            "sort": sort,
            "no_aggs": no_aggs
        }
        if company:
            params["company"] = company

        return self.get_complaints_pagination(params)

    def get_complaints_pagination(
            self,
            params: dict[str, Any],
            search_after: str | None = None,
            size: int | None = 10000
        ) -> list[dict[str, Any]]:
        """Fetch complaints with cursor-based pagination support
        
        Args:
            params (dict[str, Any]): Request parameters are passed
            search_after (str): Parameter for paginate results (combined with size)
            size (int): Parameter for paginate results (combined with search_after). Default to 10000

        Returns:
            list: list of complaints or an empty list if no records were found
        """

        params["size"] = size
        all_complaints = []

        while True:
            try:
                
                if search_after:
                    params["search_after"] = search_after

                # request
                response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
                data = response.json()
                data = {k: data[k] for k in list(data)[1:]}
                hits = data.get("hits", {}).get("hits", [])
                complaints = [hit.get("_source", {}) for hit in hits]
                if not hits: # no records
                    break

                total_available_complaints = data.get("hits", {}).get("total", {}).get("value", 0)
                all_complaints.extend(complaints)
                if len(all_complaints) >= total_available_complaints: # no more complaints to fetch
                    break
                
                # update search_after for subsequent API call
                search_after_lst = hits[-1].get("sort", [])
                search_after_lst[0] = str(search_after_lst[0])
                search_after = "_".join(search_after_lst)

            except requests.RequestException as e:
                # error message and re-raise
                logger.error(f"Error when fetching complaints: {e}")
                raise

        logger.info(f"Total complaints fetched: {len(all_complaints)}")
        return all_complaints

    def get_complaints_by_company(
        self,
        company: str | None = None,
        date_received_min: str | None = None,
        date_received_max: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch complaints for a specific company

        Args:
            company (str | None, optional): Company name to fetch. Defaults to None.
            date_received_min (str | None, optional): Minimum date received (YYYY-MM-DD). Defaults to None.
            date_received_max (str | None, optional): Maximum date received (YYYY-MM-DD). Defaults to None.

        Returns:
            list[dict[str, Any]]: List of complaints for the specified company
        """
        return self.get_complaints(
            date_received_min=date_received_min,
            date_received_max=date_received_max,
            company=company
        )
        
    def close(self):
        """Close the CFPB API session"""
        if self.session:
            self.session.close()


# if __name__ == "__main__":
#     client = CFPBClient()
#     complaints = client.get_complaints(
#         date_received_min="2026-04-01",
#         date_received_max="2026-04-01",
#         company="Kriya Capital, LLC"
#     )

#     with open("output.json", "w", encoding="utf-8") as f:
#         json.dump(complaints, f, indent=4, ensure_ascii=False)
#     print(len(complaints))
#     client.close()