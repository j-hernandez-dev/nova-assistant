"""Phase 1: characterize the legacy HTTP exposure and its removal.

The legacy checks run only while the old module exists.  The product
contracts remain active after the module is removed.
"""

import contextlib
import importlib
import importlib.util
import io
import json
import queue
import subprocess
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_cli.__main__ import _dispatch_alternate_modes
from local_cli.cli import build_parser
from local_cli.config import Config
from local_cli.tools import create_tools


_LEGACY_MONITOR_PRESENT = importlib.util.find_spec("local_cli.web_monitor") is not None


@unittest.skipUnless(_LEGACY_MONITOR_PRESENT, "legacy monitor removed in phase 1")
class TestLegacyWebMonitorExposure(unittest.TestCase):
    def test_bind_address_is_all_interfaces(self) -> None:
        monitor = importlib.import_module("local_cli.web_monitor")
        provider = MagicMock()
        provider.format_tools.return_value = []
        with (
            patch("local_cli.providers.get_provider", return_value=provider),
            patch.object(monitor, "create_tools", return_value=[]),
            patch.object(monitor, "build_system_prompt", return_value="system"),
            patch.object(monitor.http.server, "HTTPServer") as server_class,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            monitor.run_web_monitor(Config(), port=7071)
        server_class.assert_called_once_with(("0.0.0.0", 7071), monitor._Handler)

    def test_post_without_credentials_starts_agent(self) -> None:
        monitor = importlib.import_module("local_cli.web_monitor")
        handler = monitor._Handler
        handler.config = Config()
        handler.provider = MagicMock()
        handler.tools = []
        handler.tool_defs = []
        handler.tool_map = {}
        handler.skills_loader = None
        handler.event_queue = queue.Queue()
        handler.session_messages = []
        started = threading.Event()

        def finish_agent(*args):
            started.set()
            args[6].put(None)

        with patch.object(monitor, "_run_agent", side_effect=finish_agent):
            server = monitor.http.server.HTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/run",
                    data=json.dumps({"task": "characterize"}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b'"type": "config"', response.read())
                self.assertTrue(started.wait(2))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class TestWebMonitorExcludedFromProduct(unittest.TestCase):
    def test_monitor_module_is_not_importable(self) -> None:
        self.assertIsNone(importlib.util.find_spec("local_cli.web_monitor"))

    def test_monitor_cli_flags_are_rejected(self) -> None:
        parser = build_parser()
        for option in ("--web-monitor", "--web-port"):
            with self.subTest(option=option):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        parser.parse_args([option])
                self.assertEqual(error.exception.code, 2)

    def test_monitor_tool_frontend_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown tool frontend"):
            create_tools("web_monitor")

    def test_legacy_monitor_dispatch_is_inert(self) -> None:
        legacy_args = type("Args", (), {"web_monitor": True, "web_port": 7071})()
        self.assertFalse(_dispatch_alternate_modes(legacy_args, Config()))

    def test_cli_entrypoint_remains_available_without_monitor(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "local_cli", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--server", result.stdout)
        self.assertNotIn("--web-monitor", result.stdout)

    def test_server_entrypoint_remains_available_without_monitor(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "local_cli", "--server"],
            input='{"id": 17, "type": "status"}\n',
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(events[0]["type"], "ready")
        self.assertTrue(any(e.get("id") == 17 and e.get("type") == "status" for e in events))


if __name__ == "__main__":
    unittest.main()
