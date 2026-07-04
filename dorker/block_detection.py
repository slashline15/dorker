"""Heuristics for classifying whether an HTTP response indicates a block."""

from enum import Enum, auto

_CAPTCHA_MARKERS = (
    "our systems have detected unusual traffic",
    "/sorry/index",
    "verify you are a human",
    "checking your browser before accessing",
    "please complete the security check to access",
    "complete the challenge to continue",
)

# Real challenge/CAPTCHA pages are short; large pages that happen to mention
# one of the phrases above (e.g. inside an embedded i18n bundle) are not.
_MAX_CAPTCHA_PAGE_LENGTH = 20_000

_MIN_BODY_LENGTH = 200


class BlockStatus(Enum):
    OK = auto()
    RATE_LIMITED = auto()
    BLOCKED_CAPTCHA = auto()
    BLOCKED_UNKNOWN = auto()
    EMPTY = auto()


def classify_response(status_code: int, html_text: str) -> BlockStatus:
    """Classify a response using both its status code and body content.

    Content is checked first: a CAPTCHA page is often served with a normal
    200 status after a redirect, so relying on status codes alone misses it.
    """
    if len(html_text) < _MAX_CAPTCHA_PAGE_LENGTH:
        lowered = html_text.lower()
        if any(marker in lowered for marker in _CAPTCHA_MARKERS):
            return BlockStatus.BLOCKED_CAPTCHA

    if status_code == 429:
        return BlockStatus.RATE_LIMITED

    if status_code != 200:
        return BlockStatus.BLOCKED_UNKNOWN

    if len(html_text.strip()) < _MIN_BODY_LENGTH:
        return BlockStatus.EMPTY

    return BlockStatus.OK
