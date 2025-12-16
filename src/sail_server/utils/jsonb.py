# -*- coding: utf-8 -*-
# @file jsonb.py
# @brief The Json Binary Model
# @author sailing-innocent
# @date 2025-04-28
# @version 1.0
# ---------------------------------

def json_bytes_to_dict(json_bytes: bytes) -> dict:
    """
    Convert json binary to dict
    """
    import json
    import zlib
    return json.loads(zlib.decompress(json_bytes).decode("utf-8"))

def dict_to_json_bytes(data: dict) -> bytes:
    """
    Convert dict to json binary
    """
    import json
    import zlib
    return zlib.compress(json.dumps(data).encode("utf-8"))