# -*- coding: utf-8 -*-
# @file conftest.py
# @brief pytest configuration file
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------

import os
import sys
import pytest

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.env import read_env

read_env("dev")  # use dev environment for testing


@pytest.fixture
def db():
    """
    Fixture to provide a database function for testing.
    This function should be replaced with the actual database function used in your application.
    """

    from internal.db import g_db_func

    return next(g_db_func())
