"""Continuous news polling (APScheduler).  python -m app.news.scheduler

Press feeds every NEWS_PRESS_MINUTES, regulator feeds every NEWS_REGULATORS_HOURS.
Mirrors the dashboard cadence. For production, run under systemd/PM2 (see docs).
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_settings
from app.news.poller import poll


def main() -> None:
    s = get_settings()
    print(f"news scheduler: press every {s.news_press_minutes}m, regulators every {s.news_regulators_hours}h")
    print("→ initial press poll…", poll(["press"]))

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(lambda: poll(["press"]), "interval", minutes=s.news_press_minutes, id="press")
    sched.add_job(lambda: poll(["regulator"]), "interval", hours=s.news_regulators_hours, id="regulators")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
