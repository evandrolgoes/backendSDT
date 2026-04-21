import os
import sys
import threading
import time

from .services import sync_auto_contracts

SYNC_INTERVAL_SECONDS = 60
_scheduler_started = False
_scheduler_lock = threading.Lock()


def _should_start_scheduler():
    if os.environ.get("SDT_TRADINGVIEW_SYNC_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return False

    command = sys.argv[1] if len(sys.argv) > 1 else ""
    blocked_commands = {
        "makemigrations",
        "migrate",
        "collectstatic",
        "createsuperuser",
        "shell",
        "dbshell",
        "test",
        "flush",
    }
    if command in blocked_commands:
        return False

    if command == "runserver":
        # With the default Django autoreloader, only the child process should start the job.
        # When runserver is started with --noreload, RUN_MAIN is not set, so allow it.
        if "--noreload" not in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return False

    return True


def _sync_loop():
    while True:
        try:
            sync_auto_contracts()
        except Exception:
            # Keep the backend running even if an external sync fails.
            pass
        time.sleep(SYNC_INTERVAL_SECONDS)


def start_tradingview_sync_job():
    global _scheduler_started

    if not _should_start_scheduler():
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        worker = threading.Thread(
            target=_sync_loop,
            name="tradingview-sync-job",
            daemon=True,
        )
        worker.start()
        _scheduler_started = True
