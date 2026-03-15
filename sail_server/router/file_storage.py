# -*- coding: utf-8 -*-
# @file file_storage.py
# @brief File Storage Router
# @author sailing-innocent
# @date 2026-03-14
# @version 1.0
# ---------------------------------

from litestar import Router
from sail_server.controller.file_storage import FileStorageController

router = Router(
    path="/file-storage",
    route_handlers=[FileStorageController],
)
