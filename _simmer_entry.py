import sys
import threading
import time

# Print immediately — before heavy imports (pyobjc/aiohttp) begin
sys.stdout.write("\033[?25l")  # hide cursor
sys.stdout.flush()

_frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
_stop = threading.Event()

def _spin():
    i = 0
    while not _stop.is_set():
        sys.stdout.write(f"\r  {_frames[i % len(_frames)]}  starting simmer…")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1

_t = threading.Thread(target=_spin, daemon=True)
_t.start()

from simmer.__main__ import main  # noqa: E402 — heavy imports happen here

_stop.set()
_t.join()
sys.stdout.write("\r\033[2K")   # clear the spinner line
sys.stdout.write("\033[?25h")   # show cursor
sys.stdout.flush()

main()
