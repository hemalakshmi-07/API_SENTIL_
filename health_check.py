#!/usr/bin/env python3
"""API Sentinel status check.

Checks that the frontend and the API /health endpoint respond with HTTP 200
and reports response time. Exits non-zero if anything fails, so it can be
run from cron, GitHub Actions, or an uptime monitor.

Usage:
    python scripts/health_check.py
    SITE_URL=https://your-site.example SENTINEL_API_URL=https://abc.execute-api.ap-south-1.amazonaws.com/health python scripts/health_check.py
"""
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

CHECKS = {
    "frontend": os.environ.get("SITE_URL", "http://localhost:8000"),
    "api /health": os.environ.get("SENTINEL_API_URL", "http://localhost:3000/health"),
}
TIMEOUT_SECONDS = 5
SLOW_THRESHOLD_SECONDS = 2.0


def check(name, url):
    start = time.time()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
            elapsed = time.time() - start
            status = resp.status
    except urllib.error.HTTPError as e:
        return name, url, False, f"HTTP {e.code}", time.time() - start
    except Exception as e:  # DNS failure, timeout, connection refused
        return name, url, False, type(e).__name__, time.time() - start

    if status != 200:
        return name, url, False, f"HTTP {status}", elapsed
    if elapsed > SLOW_THRESHOLD_SECONDS:
        return name, url, True, f"OK but slow ({elapsed:.2f}s)", elapsed
    return name, url, True, "OK", elapsed


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"API Sentinel status check @ {now}")
    all_ok = True
    for name, url in CHECKS.items():
        name, url, ok, detail, elapsed = check(name, url)
        all_ok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<12} {detail:<22} {elapsed:.2f}s  {url}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
