# -*- coding: utf-8 -*-
# @file sample_client.py
# @brief The Sample Client for Sail Server (for local testing)
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------

import os
import requests


class SampleClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.api_endpoint = os.environ.get("API_ENDPOINT", "/api")
        self.base_url = f"http://{self.host}:{self.port}"
        self.api_url = f"{self.base_url}{self.api_endpoint}"

    def health_check(self):
        url = f"{self.base_url}/health"
        response = requests.get(url)
        expected_status = 200
        expected_data = {"status": "ok"}

        assert response.status_code == expected_status, (
            f"Expected {expected_status}, got {response.status_code}"
        )

        assert response.json() == expected_data, (
            f"Expected {expected_data}, got {response.json()}"
        )
