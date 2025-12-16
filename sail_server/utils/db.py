# -*- coding: utf-8 -*-
# @file db.py
# @brief The Database Utilities
# @author sailing-innocent
# @date 2025-04-29
# @version 1.0
# ---------------------------------

from sqlalchemy.dialects import postgresql

def show_sql(query):
    """
    Show the SQL query string.
    """
    print(query.statement.compile(compile_kwargs={"literal_binds": True},dialect=postgresql.dialect(paramstyle="named")))
