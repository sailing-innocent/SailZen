# -*- coding: utf-8 -*-
# @file conftest.py
# @brief The Configuration for pytest
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------

import os
import pytest


@pytest.fixture
def sample_client():
    """
    Fixture to provide a sample client for testing.
    This function should be replaced with the actual client used in your application.
    """
    from internal.sample_client import SampleClient

    host = os.environ.get("SERVER_HOST", "localhost")
    port = os.environ.get("SERVER_PORT", 8000)
    client = SampleClient(host, port)
    return client
