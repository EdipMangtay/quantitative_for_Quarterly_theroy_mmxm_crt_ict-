"""Polite, resumable Dukascopy downloader.

* Raw bi5 files are cached under ``data/raw/{key}`` (an empty marker ``.empty``
  is written for legitimately empty files, e.g. weekends).
* HTTP 429 is *respected*: we back off exponentially (honouring Retry-After)
  and globally slow down.  No proxies / rotation / circumvention of any kind.
* Optional S3 Requester-Pays path (documented by Dukascopy) when the user
  provides AWS credentials:  ``ASTRA_SOURCE=s3``.
"""
from __future__ import annotations

import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

from .dukascopy import HTTP_BASE, S3_BUCKET, SYMBOLS, candle_key, tick_key

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
UA = "astra6-research/0.1 (historical research; polite rate)"


class RateGate:
    """Global minimum interval between requests, adaptively widened on 429."""

    def __init__(self, min_interval: float = 4.0):
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.next_t = 0.0
        self.n429 = 0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_t)
            self.next_t = t + self.min_interval
        if t > now:
            time.sleep(t - now)

    def penalise(self, seconds: float):
        with self.lock:
            self.n429 += 1
            self.min_interval = min(self.min_interval * 1.25, 30.0)
            self.next_t = max(self.next_t, time.monotonic() + seconds)

    def reward(self):
        with self.lock:
            self.min_interval = max(self.min_interval * 0.98, 2.0)


GATE = RateGate()


def _path(key: str) -> Path:
    return RAW / key


def is_cached(key: str) -> bool:
    p = _path(key)
    return p.exists() or p.with_suffix(".empty").exists()


def fetch_http(key: str, max_tries: int = 40) -> bytes | None:
    url = f"{HTTP_BASE}/{key}"
    backoff = 30.0
    for attempt in range(max_tries):
        GATE.wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            GATE.reward()
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                wait = float(ra) if ra and ra.isdigit() else backoff
                GATE.penalise(wait)
                backoff = min(backoff * 1.5, 300)
                continue
            if e.code >= 500:
                time.sleep(5 + 5 * attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5 + 5 * attempt)
    return None


_s3 = None


def fetch_s3(key: str) -> bytes | None:
    global _s3
    import boto3
    from botocore.exceptions import ClientError
    if _s3 is None:
        _s3 = boto3.client("s3", region_name="eu-west-1")
    try:
        r = _s3.get_object(Bucket=S3_BUCKET, Key=key, RequestPayer="requester")
        return r["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return b""
        raise


def fetch(key: str) -> bool:
    if is_cached(key):
        return True
    src = os.environ.get("ASTRA_SOURCE", "http")
    data = fetch_s3(key) if src == "s3" else fetch_http(key)
    if data is None:
        return False
    p = _path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    if len(data) == 0:
        p.with_suffix(".empty").touch()
    else:
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(p)
    return True


def trading_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() != 5:  # Saturdays: index CFDs closed at Dukascopy
            yield d
        d += timedelta(days=1)


def candle_jobs(start: date, end: date, sides=("BID", "ASK"), symbols=None):
    syms = symbols or list(SYMBOLS.values())
    return [candle_key(s, d, side) for side in sides for s in syms for d in trading_days(start, end)]


def tick_jobs(start: date, end: date, ny_hours=(9, 10), symbols=None):
    """Tick files covering given NY local hours (UTC hour derived per day via tzdb)."""
    from zoneinfo import ZoneInfo
    from datetime import datetime, time as dtime
    ny = ZoneInfo("America/New_York")
    syms = symbols or list(SYMBOLS.values())
    jobs = []
    for d in trading_days(start, end):
        if d.weekday() == 6:
            continue
        for h in ny_hours:
            u = datetime.combine(d, dtime(h, 0), tzinfo=ny).astimezone(ZoneInfo("UTC"))
            for s in syms:
                jobs.append(tick_key(s, u.date(), u.hour))
    return jobs


def run(jobs, workers: int = 3, label: str = "") -> dict:
    todo = [k for k in jobs if not is_cached(k)]
    t0 = time.time()
    ok = fail = 0
    print(f"[{label}] {len(jobs)} jobs, {len(todo)} to fetch", flush=True)
    random.seed(0)
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch, k): k for k in todo}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                if f.result():
                    ok += 1
                else:
                    fail += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                print("ERR", futs[f], e, flush=True)
            if i % 25 == 0:
                el = time.time() - t0
                print(f"[{label}] {i}/{len(todo)} ok={ok} fail={fail} 429s={GATE.n429} "
                      f"interval={GATE.min_interval:.2f}s rate={i/el:.2f}/s eta={(len(todo)-i)/(i/el)/60:.0f}m",
                      flush=True)
    print(f"[{label}] done ok={ok} fail={fail} in {(time.time()-t0)/60:.1f}m", flush=True)
    return {"ok": ok, "fail": fail}


def priority_jobs(start: date, end: date):
    """Pass A (newest -> oldest): US100 BID+ASK, US500 BID.  Pass B: US30 BID,
    US500 ASK, US30 ASK.  Lets research start on a contiguous recent window
    and grow backwards while the throttled public feed is being read."""
    days = sorted(trading_days(start, end), reverse=True)
    a = [candle_key(s, d, side) for d in days for s, side in
         (("USATECHIDXUSD", "BID"), ("USA500IDXUSD", "BID"), ("USATECHIDXUSD", "ASK"))]
    b = [candle_key(s, d, side) for d in days for s, side in
         (("USA30IDXUSD", "BID"), ("USA500IDXUSD", "ASK"), ("USA30IDXUSD", "ASK"))]
    return a + b


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "candles"
    start = date(2021, 11, 7)
    end = date(2026, 11, 7)
    if what == "priority":
        run(priority_jobs(start, end), workers=1, label="PRIO")
    elif what == "candles_bid":
        run(candle_jobs(start, end, sides=("BID",)), label="BID")
    elif what == "candles_ask":
        run(candle_jobs(start, end, sides=("ASK",)), label="ASK")
    elif what == "ticks":
        run(tick_jobs(start, end), label="TICKS")
