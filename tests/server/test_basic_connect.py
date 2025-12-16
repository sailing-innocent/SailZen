# -*- coding: utf-8 -*-
# @file test_basic_connect.py
# @brief The Basic Connection Testcase
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------

import pytest


@pytest.mark.server
def test_basic_connect(sample_client):
    """
    Test the basic connection to the server.
    This test checks if the server is running and responds correctly to a health check.
    """
    sample_client.health_check()
