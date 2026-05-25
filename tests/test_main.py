"""Tests for the simmer CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import simmer.__main__ as main_mod


class TestKillPort:
    def test_kill_port_terminates_listening_pids(self):
        result = MagicMock()
        result.stdout = "123\n456\n"

        with patch("subprocess.run", return_value=result) as run:
            with patch.object(main_mod.os, "kill") as kill:
                with patch.object(main_mod.time, "sleep"):
                    count = main_mod._kill_port(4040)

        assert count == 2
        run.assert_called_once_with(
            ["lsof", "-tiTCP:4040", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        kill.assert_any_call(123, main_mod.signal.SIGTERM)
        kill.assert_any_call(456, main_mod.signal.SIGTERM)

    def test_kill_port_ignores_missing_lsof(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert main_mod._kill_port(4040) == 0


class TestMain:
    def test_kill_exits_before_backend_selection(self):
        with patch.object(main_mod, "_kill_port", return_value=1) as kill:
            with patch.object(main_mod, "_select_backend") as select_backend:
                main_mod.main(["--kill", "--port", "5050"])

        kill.assert_called_once_with(5050)
        select_backend.assert_not_called()
