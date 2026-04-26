# -*- coding: utf-8 -*-
# @file test_compatibility.py
# @brief Tests for sail.opencode.compatibility
# @author sailing-innocent
# @date 2026-04-25
# ---------------------------------
"""Unit tests for the CLI compatibility checker."""

from unittest.mock import patch, MagicMock

import pytest

from sail.opencode.compatibility import (
    CompatibilityReport,
    check_cli_compatibility,
)


class TestCompatibilityReport:
    def test_all_pass(self):
        r = CompatibilityReport(
            tool="opencode-cli",
            found=True,
            serve_help_ok=True,
            health_ok=True,
            api_ok=True,
        )
        assert r.is_compatible is True
        assert "Compatible" in r.to_text()

    def test_not_found(self):
        r = CompatibilityReport(tool="fake-tool", errors=["Command not found"])
        assert r.is_compatible is False
        assert "not found" in r.to_text()

    def test_missing_health(self):
        r = CompatibilityReport(
            tool="x",
            found=True,
            serve_help_ok=True,
            health_ok=False,
            errors=["timeout"],
        )
        assert r.is_compatible is False
        assert "timeout" in r.to_text()


class TestCheckCliCompatibility:
    @patch("sail.opencode.compatibility.shutil.which", return_value=None)
    def test_command_not_found(self, mock_which):
        report = check_cli_compatibility("missing-tool")
        assert report.found is False
        assert not report.is_compatible

    @patch("sail.opencode.compatibility.shutil.which", return_value="/usr/bin/fake")
    @patch("sail.opencode.compatibility.subprocess.run")
    def test_serve_help_fails(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        report = check_cli_compatibility("fake")
        assert report.found is True
        assert report.serve_help_ok is False
        assert not report.is_compatible

    @patch("sail.opencode.compatibility.shutil.which", return_value="/usr/bin/fake")
    @patch("sail.opencode.compatibility.subprocess.run")
    @patch("sail.opencode.compatibility.subprocess.Popen")
    @patch("sail.opencode.compatibility.check_health_sync", return_value=True)
    @patch("sail.opencode.compatibility.httpx.Client")
    def test_fully_compatible(self, mock_client_cls, mock_health, mock_popen, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="help", stderr="")

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.iter_lines.return_value = [b"data: {}", b"", b"data: {}"]
        mock_client.stream.return_value = mock_stream
        mock_client_cls.return_value = mock_client

        report = check_cli_compatibility("fake", port=12345)
        assert report.is_compatible is True
