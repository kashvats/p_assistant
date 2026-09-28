from __future__ import annotations

import random
from typing import Any


class RetryPolicy:
    """Section 75: Production-grade differentiated retry policy."""

    @staticmethod
    def evaluate(
        status_code: int | None = None,
        error: Exception | str | None = None,
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Determine whether to retry and calculate backoff delay with jitter."""
        err_str = str(error or "").lower()

        # 1. HTTP 429 / Rate Limited -> Exponential backoff with jitter
        if status_code == 429 or "rate limit" in err_str or "too many requests" in err_str:
            if attempt >= max_attempts:
                return {"should_retry": False, "delay": 0.0, "reason": "Max rate-limit retry attempts reached."}
            base = 2.0 ** attempt
            jitter = random.uniform(0.1, 0.6)
            delay = min(60.0, round(base + jitter, 3))
            return {
                "should_retry": True,
                "delay": delay,
                "reason": f"HTTP 429 / Rate limit: exponential backoff with jitter (attempt {attempt}/{max_attempts}).",
            }

        # 2. HTTP 500, 502, 503, 504 -> Server error retry
        if status_code in {500, 502, 503, 504} or "server error" in err_str or "bad gateway" in err_str:
            if attempt >= max_attempts:
                return {"should_retry": False, "delay": 0.0, "reason": "Max server error retry attempts reached."}
            delay = round(1.2 ** attempt + random.uniform(0.1, 0.4), 3)
            return {
                "should_retry": True,
                "delay": delay,
                "reason": f"Server error ({status_code}): retrying with jitter.",
            }

        # 3. Timeout -> Single retry or fallback
        if status_code == 408 or "timeout" in err_str or "timed out" in err_str:
            if attempt >= 2:
                return {"should_retry": False, "delay": 0.0, "reason": "Timeout retry limit reached; switch to fallback."}
            return {
                "should_retry": True,
                "delay": 1.0,
                "reason": "Request timed out; attempting single retry before fallback.",
            }

        # 4. HTTP 400 Bad Request -> Do not blindly retry with same invalid arguments
        if status_code == 400 or "bad request" in err_str or "invalid argument" in err_str:
            return {
                "should_retry": False,
                "delay": 0.0,
                "reason": "HTTP 400 Client error: Arguments are invalid. Do not blindly retry.",
            }

        # 5. HTTP 401 Unauthorized -> Credentials failure
        if status_code == 401 or "unauthorized" in err_str or "invalid token" in err_str:
            return {
                "should_retry": False,
                "delay": 0.0,
                "reason": "HTTP 401 Unauthorized: Invalid or missing credentials. Requires authentication update.",
            }

        # 6. HTTP 403 Forbidden -> Permission denied
        if status_code == 403 or "forbidden" in err_str or "permission denied" in err_str:
            return {
                "should_retry": False,
                "delay": 0.0,
                "reason": "HTTP 403 Forbidden: Access denied. Explicit user approval or policy permission required.",
            }

        # 7. HTTP 404 Not Found -> Do not repeatedly request nonexistent resource
        if status_code == 404 or "not found" in err_str:
            return {
                "should_retry": False,
                "delay": 0.0,
                "reason": "HTTP 404 Not Found: Resource does not exist. Do not repeatedly request.",
            }

        # Default fallback
        if attempt < max_attempts and error is not None:
            return {
                "should_retry": True,
                "delay": 1.0,
                "reason": "Transient error: general retry.",
            }

        return {"should_retry": False, "delay": 0.0, "reason": "No retry policy matched."}
