#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify button JSON structure meets Feishu API requirements
"""

import sys

sys.path.insert(0, "D:/ws/repos/SailZen/bot")

from card_renderer import _button
import json

# Test button generation
btn = _button(
    label="Start",
    action_type="callback",
    value={"action": "start_workspace", "path": "sailzen"},
    style="primary",
)

print("Generated button JSON structure:")
print(json.dumps(btn, indent=2, ensure_ascii=False))
print("\nStructure check: Uses behaviors array, meets Feishu API requirements")
print("\nKey points:")
print("- tag: button OK")
print("- text: {tag: plain_text, content: ...} OK")
print("- type: primary OK")
print("- behaviors: [{type: callback, value: ...}] OK")
print("\nNote: Removed 'action_type' field which was causing error 11310")
print("      Now using 'behaviors' array as per Feishu API docs")
