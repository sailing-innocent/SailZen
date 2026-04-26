#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file dendron_kb.py
# @brief Dendron Knowledge Base CLI - AI Native interface to Dendron Engine
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0
# ---------------------------------
"""
Dendron Knowledge Base CLI

AI-native CLI tool for querying and manipulating Dendron knowledge bases
via the Dendron Engine Server HTTP API.

Usage:
    python dendron_kb.py --ws <workspace_root> <command> [options]

Environment:
    DENDRON_ENGINE_PORT   - Engine server port (optional)
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# YAML handling (optional dependency)
# ---------------------------------------------------------------------------
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_yaml_simple(text: str) -> Dict[str, Any]:
    """Minimal YAML parser for dendron.yml (no nested structures)"""
    result: Dict[str, Any] = {}
    current_section: Optional[str] = None
    current_list: Optional[List[Any]] = None
    current_dict: Optional[Dict[str, Any]] = None
    indent_stack: List[Tuple[int, str]] = []

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(line) - len(stripped)

        # Vault list items (special handling)
        if stripped.startswith("- fsPath:"):
            if current_section == "vaults" and "workspace" in result:
                vault = {}
                # Parse this line and subsequent indented lines
                parts = stripped[1:].strip().split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    vault[key] = val
                # Read following indented lines
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    next_stripped = next_line.lstrip()
                    if not next_stripped or next_stripped.startswith("#"):
                        j += 1
                        continue
                    next_indent = len(next_line) - len(next_stripped)
                    if next_indent <= indent:
                        break
                    if next_stripped.startswith("- "):
                        break
                    parts = next_stripped.split(":", 1)
                    if len(parts) == 2:
                        vault[parts[0].strip()] = parts[1].strip().strip("\"'")
                    j += 1
                result["workspace"]["vaults"].append(vault)
                i = j
                continue

        # List item
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if current_list is not None:
                current_list.append(item)
            i += 1
            continue

        # Key-value pair
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("\"'")

            # Section header (no value)
            if not val:
                current_section = key
                if key == "vaults":
                    if "workspace" not in result:
                        result["workspace"] = {}
                    result["workspace"]["vaults"] = []
                    current_list = result["workspace"]["vaults"]
                else:
                    current_list = None
                indent_stack = [(indent, key)]
                i += 1
                continue

            # Store value
            if indent > 0 and indent_stack:
                parent_indent, parent_key = indent_stack[-1]
                if indent > parent_indent:
                    if parent_key not in result:
                        result[parent_key] = {}
                    if isinstance(result[parent_key], dict):
                        result[parent_key][key] = val
                else:
                    result[key] = val
            else:
                result[key] = val

        i += 1

    return result


def load_dendron_config(ws_root: Path) -> Dict[str, Any]:
    """Load dendron.yml configuration"""
    config_file = ws_root / "dendron.yml"
    if not config_file.exists():
        raise RuntimeError(f"No dendron.yml found in {ws_root}")

    text = config_file.read_text(encoding="utf-8")
    if HAS_YAML:
        return yaml.safe_load(text)
    return parse_yaml_simple(text)


# ---------------------------------------------------------------------------
# Engine Client
# ---------------------------------------------------------------------------


@dataclass
class NoteRef:
    """Lightweight note reference"""

    id: str
    fname: str
    title: str
    vault: str
    desc: str = ""
    updated: int = 0
    created: int = 0


class DendronEngineClient:
    """HTTP client for Dendron Engine Server"""

    def __init__(self, ws_root: str, port: Optional[int] = None):
        self.ws_root = Path(ws_root).resolve()
        self.port = port or self._discover_port()
        self.base_url = f"http://localhost:{self.port}"
        self.api_url = f"{self.base_url}/api"
        self.ws_uri = str(self.ws_root)
        self._initialized = False
        self._config: Optional[Dict[str, Any]] = None
        self._vaults: List[Dict[str, Any]] = []

    def _discover_port(self) -> int:
        """Discover engine server port from port files or environment"""
        # 1. Try workspace port file (created by VSCode plugin)
        port_file = self.ws_root / ".dendron.port"
        if port_file.exists():
            return int(port_file.read_text(encoding="utf-8").strip())

        # 2. Try CLI port file
        port_file = self.ws_root / ".dendron.port.cli"
        if port_file.exists():
            return int(port_file.read_text(encoding="utf-8").strip())

        # 3. Environment variable
        env_port = os.environ.get("DENDRON_ENGINE_PORT")
        if env_port:
            return int(env_port)

        raise RuntimeError(
            f"No engine server found for workspace: {self.ws_root}\n"
            f"Options:\n"
            f"  1. Open this workspace in VSCode with Dendron plugin active\n"
            f"  2. Set DENDRON_ENGINE_PORT environment variable\n"
            f"  3. Use --port to specify the port manually"
        )

    def _http(
        self,
        method: str,
        path: str,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to engine API"""
        url = f"{self.api_url}/{path}"
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None

        req = urllib.request.Request(
            url, data=body, headers=headers, method=method.upper()
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Server returned an error status but may have JSON error body
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                error_json = json.loads(error_body)
                # Return the error JSON so callers can handle it
                return error_json
            except json.JSONDecodeError:
                raise RuntimeError(f"HTTP {e.code}: {error_body[:500]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection failed: {e.reason}")

    def health(self) -> Dict[str, Any]:
        """Check engine server health"""
        req = urllib.request.Request(f"{self.base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    def init_workspace(self) -> Dict[str, Any]:
        """Initialize workspace with engine server"""
        self._config = load_dendron_config(self.ws_root)
        self._vaults = self._config.get("workspace", {}).get("vaults", [])

        # Normalize vaults: ensure each has fsPath
        for v in self._vaults:
            if "fsPath" not in v:
                v["fsPath"] = "."

        resp = self._http(
            "post",
            "workspace/initialize",
            {"uri": self.ws_uri, "config": {"vaults": self._vaults}},
        )

        if resp.get("error"):
            raise RuntimeError(f"Workspace init failed: {resp['error']}")

        self._initialized = True
        return resp

    def sync_workspace(self) -> Dict[str, Any]:
        """Sync workspace state from engine"""
        resp = self._http("post", "workspace/sync", {"ws": self.ws_uri})
        if resp.get("error"):
            raise RuntimeError(f"Workspace sync failed: {resp['error']}")
        self._initialized = True
        return resp

    def ensure_initialized(self) -> None:
        """Ensure workspace is initialized"""
        if self._initialized:
            return
        try:
            self.sync_workspace()
        except RuntimeError:
            self.init_workspace()

    # --- Note Queries ---

    def query_notes(self, qs: str, vault: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fuzzy query notes (uses Fuse.js index)"""
        self.ensure_initialized()
        params: Dict[str, Any] = {"qs": qs}
        if vault:
            params["vault"] = vault
        # Note: query endpoint doesn't require ws param in some versions
        # but we add it for safety
        params["ws"] = self.ws_uri
        resp = self._http("get", "note/query", params=params)
        return resp.get("data", []) or []

    def find_notes(
        self,
        fname: Optional[str] = None,
        vault: Optional[str] = None,
        exclude_stub: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find notes by exact criteria"""
        self.ensure_initialized()
        body: Dict[str, Any] = {"ws": self.ws_uri}
        if fname:
            body["fname"] = fname
        if vault:
            body["vault"] = {"fsPath": vault} if not isinstance(vault, dict) else vault
        if exclude_stub is not None:
            body["excludeStub"] = exclude_stub
        resp = self._http("post", "note/find", body)
        return resp.get("data", []) or []

    def find_notes_meta(
        self, fname: Optional[str] = None, vault: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find note metadata (without body)"""
        self.ensure_initialized()
        body: Dict[str, Any] = {"ws": self.ws_uri}
        if fname:
            body["fname"] = fname
        if vault:
            body["vault"] = {"fsPath": vault} if not isinstance(vault, dict) else vault
        resp = self._http("post", "note/findMeta", body)
        return resp.get("data", []) or []

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get full note by ID"""
        self.ensure_initialized()
        resp = self._http("get", "note/get", params={"id": note_id, "ws": self.ws_uri})
        if resp.get("error"):
            return None
        return resp.get("data")

    def get_note_meta(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get note metadata by ID"""
        self.ensure_initialized()
        resp = self._http(
            "get", "note/getMeta", params={"id": note_id, "ws": self.ws_uri}
        )
        if resp.get("error"):
            return None
        return resp.get("data")

    def bulk_get_notes(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple notes by ID"""
        self.ensure_initialized()
        resp = self._http("get", "note/bulkGet", params={"ids": ids, "ws": self.ws_uri})
        return resp.get("data", []) or []

    def bulk_get_notes_meta(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple note metadata by ID"""
        self.ensure_initialized()
        resp = self._http(
            "get", "note/bulkGetMeta", params={"ids": ids, "ws": self.ws_uri}
        )
        return resp.get("data", []) or []

    def render_note(self, note_id: str, flavor: str = "PREVIEW") -> str:
        """Render note to HTML"""
        self.ensure_initialized()
        resp = self._http(
            "post", "note/render", {"id": note_id, "ws": self.ws_uri, "flavor": flavor}
        )
        return resp.get("data", "")

    def get_note_blocks(
        self, note_id: str, filter_by_anchor_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get note blocks (headers, anchors)"""
        self.ensure_initialized()
        params: Dict[str, Any] = {"id": note_id, "ws": self.ws_uri}
        if filter_by_anchor_type:
            params["filterByAnchorType"] = filter_by_anchor_type
        resp = self._http("get", "note/blocks", params=params)
        return resp.get("data", []) or []

    # --- Note Mutations ---

    def write_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a note"""
        self.ensure_initialized()
        resp = self._http("post", "note/write", {"ws": self.ws_uri, "node": note})
        return resp

    def delete_note(self, note_id: str, meta_only: bool = False) -> Dict[str, Any]:
        """Delete a note"""
        self.ensure_initialized()
        resp = self._http(
            "post",
            "note/delete",
            {"ws": self.ws_uri, "id": note_id, "opts": {"metaOnly": meta_only}},
        )
        return resp

    def rename_note(
        self,
        old_fname: str,
        new_fname: str,
        old_vault_name: Optional[str] = None,
        new_vault_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rename a note"""
        self.ensure_initialized()
        resp = self._http(
            "post",
            "note/rename",
            {
                "ws": self.ws_uri,
                "oldLoc": {"fname": old_fname, "vaultName": old_vault_name},
                "newLoc": {
                    "fname": new_fname,
                    "vaultName": new_vault_name or old_vault_name,
                },
            },
        )
        return resp

    def bulk_write_notes(self, notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Write multiple notes at once"""
        self.ensure_initialized()
        resp = self._http(
            "post", "note/bulkAdd", {"ws": self.ws_uri, "opts": {"notes": notes}}
        )
        return resp

    # --- Schema Operations ---

    def query_schema(self, qs: str) -> List[Dict[str, Any]]:
        """Query schemas"""
        self.ensure_initialized()
        resp = self._http("post", "schema/query", {"qs": qs, "ws": self.ws_uri})
        return resp.get("data", []) or []

    def get_schema(self, schema_id: str) -> Optional[Dict[str, Any]]:
        """Get schema by ID"""
        self.ensure_initialized()
        resp = self._http(
            "get", "schema/get", params={"id": schema_id, "ws": self.ws_uri}
        )
        if resp.get("error"):
            return None
        return resp.get("data")

    # --- Config ---

    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get workspace config"""
        resp = self._http("get", "config/get", params={"ws": self.ws_uri})
        if resp.get("error"):
            return None
        return resp.get("data")

    # --- Utilities ---

    def resolve_note(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Resolve a note identifier (ID or fname) to a note"""
        # Try as ID first
        note = self.get_note(identifier)
        if note:
            return note
        # Try as fname
        notes = self.find_notes(fname=identifier)
        if notes:
            return self.get_note(notes[0]["id"])
        # Try fuzzy match
        notes = self.query_notes(identifier)
        if notes:
            return self.get_note(notes[0]["id"])
        return None

    def get_all_notes_meta(self) -> List[Dict[str, Any]]:
        """Get metadata for all notes"""
        self.ensure_initialized()
        resp = self._http(
            "post", "note/findMeta", {"ws": self.ws_uri, "excludeStub": False}
        )
        return resp.get("data", []) or []

    def get_vaults(self) -> List[Dict[str, Any]]:
        """Get workspace vaults"""
        if not self._vaults:
            self._config = load_dendron_config(self.ws_root)
            self._vaults = self._config.get("workspace", {}).get("vaults", [])
        return self._vaults


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def fmt_note_meta(note: Dict[str, Any]) -> str:
    """Format note metadata as a single line"""
    fid = note.get("id", "?")[:8]
    fname = note.get("fname", "?")
    title = note.get("title", "")
    vault = note.get("vault", {})
    vname = vault.get("name", vault.get("fsPath", "?"))
    updated = note.get("updated", 0)
    date_str = (
        time.strftime("%Y-%m-%d", time.localtime(updated / 1000)) if updated else "?"
    )
    return f"{fid:<8} {date_str:<12} {vname:<15} {fname:<40} {title}"


def fmt_note_full(note: Dict[str, Any], format_type: str = "markdown") -> str:
    """Format full note for display"""
    if format_type == "json":
        return json.dumps(note, indent=2, ensure_ascii=False)

    if format_type == "html":
        # HTML rendering should be done via render_note
        return note.get("body", "")

    # Markdown format
    lines = []
    lines.append("---")
    lines.append(f"id: {note.get('id', '')}")
    lines.append(f"title: {note.get('title', '')}")
    if note.get("desc"):
        lines.append(f"desc: {note['desc']}")
    lines.append(f"fname: {note.get('fname', '')}")
    vault = note.get("vault", {})
    lines.append(f"vault: {vault.get('name', vault.get('fsPath', ''))}")
    if note.get("created"):
        lines.append(f"created: {note['created']}")
    if note.get("updated"):
        lines.append(f"updated: {note['updated']}")
    if note.get("tags"):
        tags = note["tags"]
        if isinstance(tags, list):
            lines.append(f"tags: {tags}")
        else:
            lines.append(f"tags: {tags}")
    if note.get("schema"):
        lines.append(f"schema: {note['schema']}")
    lines.append("---")
    lines.append("")
    lines.append(note.get("body", ""))
    return "\n".join(lines)


def write_note_to_file(note: Dict[str, Any], output_dir: Path, fmt: str = "md") -> Path:
    """Write a note to a file"""
    fname = note.get("fname", note.get("id", "unknown"))
    safe_name = fname.replace(".", "_")

    if fmt == "json":
        filepath = output_dir / f"{safe_name}.json"
        filepath.write_text(
            json.dumps(note, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    elif fmt == "html":
        filepath = output_dir / f"{safe_name}.html"
        filepath.write_text(note.get("body", ""), encoding="utf-8")
    else:
        filepath = output_dir / f"{safe_name}.md"
        filepath.write_text(fmt_note_full(note, "markdown"), encoding="utf-8")

    return filepath


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_status(client: DendronEngineClient, _args: argparse.Namespace) -> int:
    """Check engine server status"""
    try:
        health = client.health()
        print(f"Engine Server: OK")
        print(f"  Port: {client.port}")
        print(f"  Health: {health}")
    except RuntimeError as e:
        print(f"Engine Server: NOT REACHABLE")
        print(f"  Error: {e}")
        return 1

    try:
        version_req = urllib.request.Request(f"{client.base_url}/version")
        with urllib.request.urlopen(version_req, timeout=5) as resp:
            version_data = json.loads(resp.read().decode())
            print(f"  Version: {version_data.get('version', 'unknown')}")
    except Exception:
        pass

    print(f"\nWorkspace: {client.ws_root}")
    try:
        config = load_dendron_config(client.ws_root)
        vaults = config.get("workspace", {}).get("vaults", [])
        print(f"  Vaults ({len(vaults)}):")
        for v in vaults:
            print(
                f"    - {v.get('name', v.get('fsPath', '?'))} ({v.get('fsPath', '')})"
            )
    except RuntimeError as e:
        print(f"  Config: {e}")
    return 0


def cmd_init(client: DendronEngineClient, _args: argparse.Namespace) -> int:
    """Initialize workspace"""
    try:
        resp = client.init_workspace()
        notes = resp.get("data", {}).get("notes", {})
        print(f"Workspace initialized: {client.ws_root}")
        print(f"Notes loaded: {len(notes)}")
        return 0
    except RuntimeError as e:
        print(f"Init failed: {e}", file=sys.stderr)
        return 1


def cmd_query(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Query notes"""
    try:
        notes = client.query_notes(args.qs, vault=args.vault)
        if args.json:
            print(json.dumps(notes, indent=2, ensure_ascii=False))
            return 0

        print(f"Found {len(notes)} note(s) for query: '{args.qs}'")
        print(f"{'ID':<8} {'Updated':<12} {'Vault':<15} {'FName':<40} Title")
        print("-" * 100)
        for note in notes[: args.limit]:
            print(fmt_note_meta(note))
        if len(notes) > args.limit:
            print(f"... and {len(notes) - args.limit} more")
        return 0
    except RuntimeError as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return 1


def cmd_find(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Find notes by exact criteria"""
    try:
        notes = client.find_notes(
            fname=args.fname, vault=args.vault, exclude_stub=not args.include_stubs
        )
        if args.json:
            print(json.dumps(notes, indent=2, ensure_ascii=False))
            return 0

        print(f"Found {len(notes)} note(s)")
        print(f"{'ID':<8} {'Updated':<12} {'Vault':<15} {'FName':<40} Title")
        print("-" * 100)
        for note in notes:
            print(fmt_note_meta(note))
        return 0
    except RuntimeError as e:
        print(f"Find failed: {e}", file=sys.stderr)
        return 1


def cmd_get(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Get note content"""
    try:
        note = client.resolve_note(args.note)
        if not note:
            print(f"Note not found: {args.note}", file=sys.stderr)
            return 1

        if args.format == "html":
            html = client.render_note(note["id"])
            print(html)
        else:
            print(fmt_note_full(note, args.format))
        return 0
    except RuntimeError as e:
        print(f"Get failed: {e}", file=sys.stderr)
        return 1


def cmd_export(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Export notes to directory"""
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.query:
            notes = client.query_notes(args.query)
        elif args.fname:
            notes = client.find_notes(fname=args.fname)
        else:
            # Export all notes metadata, then fetch full
            notes_meta = client.get_all_notes_meta()
            print(f"Exporting {len(notes_meta)} notes...")
            ids = [n["id"] for n in notes_meta]
            # Batch fetch
            BATCH = 50
            notes = []
            for i in range(0, len(ids), BATCH):
                batch = ids[i : i + BATCH]
                notes.extend(client.bulk_get_notes(batch))
                print(f"  Fetched {min(i + BATCH, len(ids))}/{len(ids)}")

        exported = 0
        for note in notes:
            try:
                # For md/json export, we need full note body
                if args.format in ("md", "markdown") and not note.get("body"):
                    full_note = client.get_note(note["id"])
                    if full_note:
                        note = full_note
                write_note_to_file(note, output_dir, args.format)
                exported += 1
            except Exception as e:
                print(
                    f"  Failed to export {note.get('fname', '?')}: {e}", file=sys.stderr
                )

        print(f"Exported {exported} note(s) to {output_dir}")
        return 0
    except RuntimeError as e:
        print(f"Export failed: {e}", file=sys.stderr)
        return 1


def cmd_create(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Create a new note"""
    try:
        vaults = client.get_vaults()
        target_vault = args.vault
        if not target_vault and vaults:
            target_vault = vaults[0].get("fsPath", ".")

        now = int(time.time() * 1000)

        body = ""
        if args.body:
            if args.body.startswith("@"):
                body_path = Path(args.body[1:])
                if body_path.exists():
                    body = body_path.read_text(encoding="utf-8")
                else:
                    print(f"Body file not found: {body_path}", file=sys.stderr)
                    return 1
            else:
                body = args.body

        note = {
            "id": str(uuid.uuid4()),
            "title": args.title or args.fname.replace(".", " ").title(),
            "desc": args.desc or "",
            "fname": args.fname,
            "body": body,
            "vault": {"fsPath": target_vault, "name": target_vault},
            "created": now,
            "updated": now,
            "links": [],
            "anchors": {},
            "children": [],
            "parent": None,
            "type": "note",
            "data": {},
        }

        resp = client.write_note(note)
        if resp.get("error"):
            print(f"Create failed: {resp['error']}", file=sys.stderr)
            return 1

        print(f"Created note: {args.fname}")
        print(f"  ID: {note['id']}")
        print(f"  Vault: {target_vault}")
        return 0
    except RuntimeError as e:
        print(f"Create failed: {e}", file=sys.stderr)
        return 1


def cmd_update(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Update an existing note"""
    try:
        note = client.resolve_note(args.note)
        if not note:
            print(f"Note not found: {args.note}", file=sys.stderr)
            return 1

        if args.body:
            if args.body.startswith("@"):
                body_path = Path(args.body[1:])
                if body_path.exists():
                    note["body"] = body_path.read_text(encoding="utf-8")
                else:
                    print(f"Body file not found: {body_path}", file=sys.stderr)
                    return 1
            else:
                note["body"] = args.body

        if args.title:
            note["title"] = args.title

        if args.desc is not None:
            note["desc"] = args.desc

        note["updated"] = int(time.time() * 1000)

        resp = client.write_note(note)
        if resp.get("error"):
            print(f"Update failed: {resp['error']}", file=sys.stderr)
            return 1

        print(f"Updated note: {note['fname']}")
        return 0
    except RuntimeError as e:
        print(f"Update failed: {e}", file=sys.stderr)
        return 1


def cmd_delete(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Delete a note"""
    try:
        note = client.resolve_note(args.note)
        if not note:
            print(f"Note not found: {args.note}", file=sys.stderr)
            return 1

        resp = client.delete_note(note["id"], meta_only=args.meta_only)
        if resp.get("error"):
            print(f"Delete failed: {resp['error']}", file=sys.stderr)
            return 1

        print(f"Deleted note: {note['fname']} ({note['id']})")
        return 0
    except RuntimeError as e:
        print(f"Delete failed: {e}", file=sys.stderr)
        return 1


def cmd_rename(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Rename a note"""
    try:
        resp = client.rename_note(
            args.from_fname,
            args.to_fname,
            old_vault_name=args.vault,
            new_vault_name=args.to_vault,
        )
        if resp.get("error"):
            print(f"Rename failed: {resp['error']}", file=sys.stderr)
            return 1

        print(f"Renamed: {args.from_fname} -> {args.to_fname}")
        if resp.get("data"):
            changes = resp["data"]
            print(f"  {len(changes)} note(s) affected")
        return 0
    except RuntimeError as e:
        print(f"Rename failed: {e}", file=sys.stderr)
        return 1


def cmd_stats(client: DendronEngineClient, _args: argparse.Namespace) -> int:
    """Show knowledge base statistics"""
    try:
        notes = client.get_all_notes_meta()
        vaults = client.get_vaults()

        total = len(notes)
        stubs = sum(1 for n in notes if n.get("stub"))
        with_links = sum(1 for n in notes if n.get("links"))
        with_schema = sum(1 for n in notes if n.get("schema"))

        # Group by vault
        vault_counts: Dict[str, int] = {}
        for n in notes:
            v = n.get("vault", {})
            vname = v.get("name", v.get("fsPath", "unknown"))
            vault_counts[vname] = vault_counts.get(vname, 0) + 1

        print(f"Knowledge Base Statistics")
        print(f"=" * 40)
        print(f"Workspace: {client.ws_root}")
        print(f"Vaults: {len(vaults)}")
        print(f"Total notes: {total}")
        print(f"  Stubs: {stubs}")
        print(f"  With links: {with_links}")
        print(f"  With schema: {with_schema}")
        print(f"\nNotes by vault:")
        for vname, count in sorted(vault_counts.items()):
            print(f"  {vname}: {count}")

        # Recent updates
        sorted_notes = sorted(notes, key=lambda n: n.get("updated", 0), reverse=True)
        print(f"\nRecently updated:")
        for n in sorted_notes[:10]:
            updated = n.get("updated", 0)
            date_str = (
                time.strftime("%Y-%m-%d", time.localtime(updated / 1000))
                if updated
                else "?"
            )
            print(f"  {date_str} {n.get('fname', '?'):<40} {n.get('title', '')}")

        return 0
    except RuntimeError as e:
        print(f"Stats failed: {e}", file=sys.stderr)
        return 1


def cmd_blocks(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Get note blocks/anchors"""
    try:
        note = client.resolve_note(args.note)
        if not note:
            print(f"Note not found: {args.note}", file=sys.stderr)
            return 1

        blocks = client.get_note_blocks(note["id"], args.filter)
        if args.json:
            print(json.dumps(blocks, indent=2, ensure_ascii=False))
            return 0

        print(f"Blocks in {note['fname']}:")
        for block in blocks:
            btype = block.get("type", "?")
            text = block.get("text", "")[:60]
            anchor = block.get("anchor", {})
            anchor_val = anchor.get("value", "") if anchor else ""
            print(f"  [{btype:<10}] #{anchor_val:<20} {text}")
        return 0
    except RuntimeError as e:
        print(f"Blocks failed: {e}", file=sys.stderr)
        return 1


def cmd_backlinks(client: DendronEngineClient, args: argparse.Namespace) -> int:
    """Show backlinks for a note"""
    try:
        note = client.resolve_note(args.note)
        if not note:
            print(f"Note not found: {args.note}", file=sys.stderr)
            return 1

        links = note.get("links", [])
        backlinks = [l for l in links if l.get("type") == "backlink"]

        print(f"Backlinks for {note['fname']} ({len(backlinks)}):")
        for link in backlinks:
            from_note = link.get("from", {})
            from_fname = from_note.get("fname", "?")
            from_alias = from_note.get("alias", "")
            print(f"  {from_fname}", end="")
            if from_alias and from_alias != from_fname:
                print(f" (alias: {from_alias})", end="")
            print()
        return 0
    except RuntimeError as e:
        print(f"Backlinks failed: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dendron Knowledge Base CLI - AI Native knowledge base interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ws ~/notes status
  %(prog)s --ws ~/notes query "daily journal"
  %(prog)s --ws ~/notes get daily.journal.2024.01.01
  %(prog)s --ws ~/notes export -o ./backup --query "project"
  %(prog)s --ws ~/notes create --fname ideas.ai-agent --title "AI Agent Ideas"
  %(prog)s --ws ~/notes update daily.journal.today --body "@new_content.md"
  %(prog)s --ws ~/notes stats

Environment:
  DENDRON_ENGINE_PORT   Engine server port (auto-detected from .dendron.port)
        """,
    )
    parser.add_argument(
        "--ws",
        "-w",
        default=os.getcwd(),
        help="Workspace root path (default: current directory)",
    )
    parser.add_argument(
        "--port", "-p", type=int, help="Engine server port (overrides auto-discovery)"
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Check engine server and workspace status")

    # init
    sub.add_parser("init", help="Initialize workspace with engine server")

    # query
    q = sub.add_parser("query", help="Fuzzy search notes (Fuse.js)")
    q.add_argument("qs", help="Query string")
    q.add_argument("--vault", help="Filter by vault")
    q.add_argument("--limit", "-n", type=int, default=50, help="Max results")
    q.add_argument("--json", action="store_true", help="Output JSON")

    # find
    f = sub.add_parser("find", help="Find notes by exact criteria")
    f.add_argument("--fname", help="Note filename (hierarchy)")
    f.add_argument("--vault", help="Filter by vault")
    f.add_argument("--include-stubs", action="store_true", help="Include stub notes")
    f.add_argument("--json", action="store_true", help="Output JSON")

    # get
    g = sub.add_parser("get", help="Get note content")
    g.add_argument("note", help="Note ID or fname")
    g.add_argument(
        "--format",
        choices=["markdown", "json", "html"],
        default="markdown",
        help="Output format",
    )

    # export
    e = sub.add_parser("export", help="Export notes to directory")
    e.add_argument("--query", "-q", help="Query to filter notes")
    e.add_argument("--fname", help="Filename pattern to filter")
    e.add_argument("--output", "-o", required=True, help="Output directory")
    e.add_argument(
        "--format", choices=["md", "json", "html"], default="md", help="Export format"
    )

    # create
    c = sub.add_parser("create", help="Create a new note")
    c.add_argument("--fname", required=True, help="Note filename (e.g., ideas.new)")
    c.add_argument("--title", help="Note title")
    c.add_argument("--desc", help="Note description")
    c.add_argument("--body", help="Note body (use @file to read from file)")
    c.add_argument("--vault", help="Target vault")

    # update
    u = sub.add_parser("update", help="Update an existing note")
    u.add_argument("note", help="Note ID or fname")
    u.add_argument("--body", help="New body (use @file to read from file)")
    u.add_argument("--title", help="New title")
    u.add_argument("--desc", help="New description")

    # delete
    d = sub.add_parser("delete", help="Delete a note")
    d.add_argument("note", help="Note ID or fname")
    d.add_argument(
        "--meta-only", action="store_true", help="Only delete metadata, keep file"
    )

    # rename
    r = sub.add_parser("rename", help="Rename a note")
    r.add_argument("--from", dest="from_fname", required=True, help="Current fname")
    r.add_argument("--to", dest="to_fname", required=True, help="New fname")
    r.add_argument("--vault", help="Source vault name")
    r.add_argument("--to-vault", help="Target vault name")

    # stats
    sub.add_parser("stats", help="Show knowledge base statistics")

    # blocks
    b = sub.add_parser("blocks", help="Get note blocks/anchors")
    b.add_argument("note", help="Note ID or fname")
    b.add_argument(
        "--filter", choices=["header", "block"], help="Filter by anchor type"
    )
    b.add_argument("--json", action="store_true", help="Output JSON")

    # backlinks
    bl = sub.add_parser("backlinks", help="Show backlinks for a note")
    bl.add_argument("note", help="Note ID or fname")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Create client
    try:
        client = DendronEngineClient(args.ws, args.port)
    except RuntimeError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        return 1

    # Route commands
    commands = {
        "status": cmd_status,
        "init": cmd_init,
        "query": cmd_query,
        "find": cmd_find,
        "get": cmd_get,
        "export": cmd_export,
        "create": cmd_create,
        "update": cmd_update,
        "delete": cmd_delete,
        "rename": cmd_rename,
        "stats": cmd_stats,
        "blocks": cmd_blocks,
        "backlinks": cmd_backlinks,
    }

    handler = commands.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return handler(client, args)


if __name__ == "__main__":
    sys.exit(main())
