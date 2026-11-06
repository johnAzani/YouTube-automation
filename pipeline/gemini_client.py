"""One Gemini client, with a deadline on every request.

Why this file exists
--------------------
On 2 November 2026 the long-form release step burned its entire 90-minute cap
(`41495990952`, 17:59:57 → 19:30:09) and was killed mid-render. The measured
encode for a 5:22 edition is ~22 minutes, speech is ~2, alignment is a few, the
upload is a few — so roughly an hour went somewhere that printed nothing.

The one place that can swallow an hour without a single log line is a socket.
`genai.Client(api_key=...)` with no `http_options` inherits the library's own
timeouts and its own retry policy. Every TTS chunk, every brain call and every
reply is a separate HTTPS request; a stalled connection on any one of them
blocks the step silently, and the step's timeout is the only thing that ever
notices. That is exactly the shape of the failure: a step that ends at its cap
rather than at an error.

So: every client in this repo comes from `make_client()`, which sets

  * a hard per-request timeout (`GEMINI_HTTP_TIMEOUT_SECONDS`, default 180s),
  * a bounded retry count, and
  * the same values whether it is the voice, the brain or the reply writer.

A stall now raises `GeminiRequestTimedOut` at the stage that caused it, which
the release reports as `✗ speech synthesis …` instead of dying as a blank
90-minute timeout.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

#: Per-request ceiling. A single Gemini TTS call for one ~450-character chunk
#: normally answers in well under 30 seconds; three minutes is generous enough
#: to survive a slow day and short enough that a dead socket is a named failure
#: rather than a 90-minute one.
DEFAULT_HTTP_TIMEOUT_SECONDS = 180

#: Retries the SDK itself performs on 5xx/429 before it gives up. Kept small and
#: explicit: our own rate-limit handling (quota_handler) is the authority on 429.
DEFAULT_HTTP_ATTEMPTS = 2


class GeminiRequestTimedOut(RuntimeError):
    """A Gemini request did not answer inside the configured deadline."""


def http_timeout_seconds() -> int:
    raw = os.environ.get("GEMINI_HTTP_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_HTTP_TIMEOUT_SECONDS
    try:
        value = int(float(raw))
    except ValueError:
        return DEFAULT_HTTP_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_HTTP_TIMEOUT_SECONDS


def http_options(attempts: int | None = None):
    """`types.HttpOptions` carrying the timeout and retry budget.

    Imported lazily so that importing this module never requires `google-genai`
    (the watchdog and the test suite import pipeline modules freely).

    `attempts=1` disables the SDK's own retries. That matters where the caller has a
    retry loop of its own: the SDK retries 5xx (including 503) *before* the caller
    sees the error, so the two multiply. On 6 November a brain call could issue ten
    requests — SDK 2 attempts × our 5 — against a model whose whole free-tier day is
    20 requests. One retry authority per call, chosen by the caller.

    `http_status_codes` deliberately omits 429: a quota refusal must reach
    `quota_handler`, which paces the day, rather than be retried inside the socket.
    """
    from google.genai import types

    attempts = attempts or DEFAULT_HTTP_ATTEMPTS
    if attempts is None:
        attempts = DEFAULT_HTTP_ATTEMPTS
    raw = os.environ.get("GEMINI_HTTP_ATTEMPTS", "").strip()
    if raw and attempts == DEFAULT_HTTP_ATTEMPTS:
        try:
            attempts = max(1, int(raw))
        except ValueError:
            pass
    try:
        retry = types.HttpRetryOptions(
            attempts=attempts,
            initial_delay=2.0,
            max_delay=30.0,
            exp_base=2.0,
            jitter=0.2,
            http_status_codes=[408, 500, 502, 503, 504],
        )
    except Exception:  # noqa: BLE001 - older/newer SDK shape; timeout matters more
        retry = None
    kwargs = {"timeout": http_timeout_seconds() * 1000}
    if retry is not None:
        kwargs["retry_options"] = retry
    return types.HttpOptions(**kwargs)


def make_client(api_key: str | None = None, attempts: int | None = None):
    """A `genai.Client` that cannot hang for longer than the timeout above."""
    from google import genai

    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key, http_options=http_options(attempts))


@contextmanager
def hard_deadline(seconds: float, what: str):
    """A wall-clock kill for a single call, enforced by the interpreter.

    On 3 November run `41560585702` sat inside one speech-synthesis call for 170
    minutes — the step's whole budget — despite `HttpOptions.timeout` being set
    to 180s. The cause is in the library: the `interactions` transport ships
    `httpx.Timeout(timeout=None, connect=5.0)`, so connecting is bounded and
    **reading is not**. A stalled response therefore waits forever, and no
    option we pass to `genai.Client` changes it.

    So the bound is enforced here instead, with `SIGALRM`, which no transport can
    ignore. This is a last line of defence, not a substitute for a real timeout:
    it is a no-op off the main thread and off Unix, and it runs *in addition to*
    the per-request timeout that paths honouring it will hit first.
    """
    import signal
    import threading

    usable = (hasattr(signal, "SIGALRM") and seconds and seconds > 0
              and threading.current_thread() is threading.main_thread())
    if not usable:  # pragma: no cover - threads/Windows keep the old behaviour
        yield
        return

    def _fire(signum, frame):  # noqa: ANN001 - signal handler signature
        raise GeminiRequestTimedOut(
            f"{what} did not return within {seconds:g}s and was abandoned. "
            f"A stalled response is a failure, not a slow success."
        )

    previous = signal.signal(signal.SIGALRM, _fire)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def is_timeout_error(exc: BaseException) -> bool:
    """Best-effort classification of a transport timeout, for clearer messages."""
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in ("timeout", "timed out", "readtimeout",
                                             "connecttimeout", "deadline"))


class Deadline:
    """A wall-clock budget for a multi-call stage, such as chunked TTS.

    A per-request timeout bounds one call; it does not bound twelve of them. This
    bounds the stage: when the budget is gone, the stage fails with the chunk it
    reached so the log says what happened.
    """

    def __init__(self, seconds: float, what: str):
        import time

        self._time = time
        self.seconds = float(seconds)
        self.what = what
        self.started = time.monotonic()

    def elapsed(self) -> float:
        return self._time.monotonic() - self.started

    def remaining(self) -> float:
        return self.seconds - self.elapsed()

    def expired(self) -> bool:
        return self.remaining() <= 0

    def check(self, detail: str = "") -> None:
        if self.expired():
            suffix = f" ({detail})" if detail else ""
            raise GeminiRequestTimedOut(
                f"{self.what} ran past its {self.seconds / 60:.0f}-minute budget"
                f"{suffix}; {self.elapsed() / 60:.1f} minutes elapsed. "
                f"Raise GEMINI_STAGE_BUDGET_SECONDS if this is genuinely slow."
            )


def stage_budget_seconds(default: float) -> float:
    raw = os.environ.get("GEMINI_STAGE_BUDGET_SECONDS", "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default
