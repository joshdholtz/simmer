"""Shared fixtures and helpers for simmer tests."""
from __future__ import annotations
import subprocess
from unittest.mock import MagicMock

from simmer.backend_base import SimDevice


def make_device(udid="ABC123", name="iPhone 15 Pro", width=393, height=852) -> SimDevice:
    return SimDevice(udid=udid, name=name, width=width, height=height)


def make_completed_process(stdout=b"", stderr=b"", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r
