# -*- coding: utf-8 -*-
# @file test_db_read.py
# @brief Test the read_weight function
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------

from internal.model.health import read_weights_impl


def test_db_read(db):
    weights = read_weights_impl(db, skip=0, limit=10)
    print(weights)
    assert len(weights) == 10
