from __future__ import annotations

import time


class PoliteThrottle:
    def __init__(self, delay_seconds: float = 2, rate_limit_per_minute: int | None = None) -> None:
        self.delay_seconds = delay_seconds
        self.min_interval = 60 / rate_limit_per_minute if rate_limit_per_minute else delay_seconds
        self.last_request_at = 0.0

    def wait(self) -> None:
        interval = max(self.delay_seconds, self.min_interval)
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self.last_request_at = time.monotonic()
