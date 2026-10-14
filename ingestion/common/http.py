"""Shared HTTP session for API clients: retries with backoff, a default timeout and a project User-Agent."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Nexus-Project/1.0 (job postings analytics; learning project)"
DEFAULT_TIMEOUT = 30  # seconds per request
RETRY_STATUSES = (429, 500, 502, 503, 504)  # rate limited or temporary server errors


class _TimeoutAdapter(HTTPAdapter):
    """Applies a default timeout to every request that doesn't set its own."""

    def __init__(self, *args, timeout: float, **kwargs):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


def build_session(
    retries: int = 5,
    backoff_factor: float = 2.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> requests.Session:
    """Return a session that retries GETs on 429/5xx, waiting longer each time and honouring Retry-After.

    After the last retry the final response is returned as-is, so callers should use raise_for_status().
    """
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = _TimeoutAdapter(max_retries=retry, timeout=timeout)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session
