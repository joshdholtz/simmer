from __future__ import annotations
import threading
from typing import Optional
from .backend_base import SimDevice


class MultiBackend:
    """Combines multiple backends, routing each call to the right one by UDID."""

    def __init__(self, backends: list):
        self._backends = backends
        self._udid_map: dict[str, object] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        names = [b.name for b in self._backends]
        return " + ".join(names)

    def list_sims(self) -> list[SimDevice]:
        sims = []
        new_map: dict[str, object] = {}
        for b in self._backends:
            try:
                for s in b.list_sims():
                    new_map[s.udid] = b
                    sims.append(s)
            except Exception:
                pass
        with self._lock:
            self._udid_map = new_map
        return sims

    def _backend_for(self, udid: str):
        with self._lock:
            if udid in self._udid_map:
                return self._udid_map[udid]
        # fallback: rebuild the map
        self.list_sims()
        with self._lock:
            return self._udid_map.get(udid, self._backends[0])

    def capture(self, udid: str, quality: int) -> Optional[bytes]:
        return self._backend_for(udid).capture(udid, quality)

    def tap(self, udid: str, nx: float, ny: float, dev_w: int, dev_h: int) -> None:
        self._backend_for(udid).tap(udid, nx, ny, dev_w, dev_h)

    def drag(self, udid: str, nx1: float, ny1: float, nx2: float, ny2: float, dev_w: int, dev_h: int) -> None:
        self._backend_for(udid).drag(udid, nx1, ny1, nx2, ny2, dev_w, dev_h)

    def key(self, udid: str, k: str) -> None:
        self._backend_for(udid).key(udid, k)

    def text(self, udid: str, t: str) -> None:
        self._backend_for(udid).text(udid, t)

    def home(self, udid: str) -> None:
        self._backend_for(udid).home(udid)

    def rotate(self, udid: str) -> None:
        self._backend_for(udid).rotate(udid)

    def appearance(self, udid: str, mode: str) -> None:
        self._backend_for(udid).appearance(udid, mode)
