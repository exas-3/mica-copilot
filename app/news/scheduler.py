"""Continuous news polling.  python -m app.news.scheduler

Press feeds every NEWS_PRESS_MINUTES, regulator feeds every NEWS_REGULATORS_HOURS.
Mirrors the dashboard cadence. For production, run under systemd/PM2 (see docs).

A single long-running process keeps the local embedder warm (loading mxbai costs
~40s + ~2GB, so a per-poll oneshot would be wasteful). Uses a plain monotonic-clock
loop rather than APScheduler — its BlockingScheduler does not reliably fire jobs under
Python 3.14 (thread-wait regression), whereas time.sleep is rock-solid everywhere.
"""
from __future__ import annotations

import time

from app.config import get_settings
from app.news.poller import poll


def main() -> None:
    s = get_settings()
    press_s = max(30, int(round(s.news_press_minutes * 60)))
    reg_s = max(press_s, int(round(s.news_regulators_hours * 3600)))
    print(f"news scheduler: press every {s.news_press_minutes}m, regulators every {s.news_regulators_hours}h", flush=True)
    print("→ initial press poll…", poll(["press"]), flush=True)
    print("→ initial regulator poll…", poll(["regulator"]), flush=True)

    last_reg = time.monotonic()
    try:
        while True:
            time.sleep(press_s)
            print("→ press poll…", poll(["press"]), flush=True)
            if time.monotonic() - last_reg >= reg_s:
                print("→ regulator poll…", poll(["regulator"]), flush=True)
                last_reg = time.monotonic()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
