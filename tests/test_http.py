from requests.adapters import HTTPAdapter

from ingestion.common.http import RETRY_STATUSES, USER_AGENT, build_session


def test_session_sends_project_user_agent():
    assert build_session().headers["User-Agent"] == USER_AGENT


def test_session_retries_gets_on_rate_limit_and_server_errors():
    retry = build_session(retries=3).get_adapter("https://jobicy.com/api").max_retries

    assert retry.total == 3
    assert set(retry.status_forcelist) == set(RETRY_STATUSES)
    assert 429 in retry.status_forcelist
    assert retry.allowed_methods == frozenset({"GET"})
    assert retry.respect_retry_after_header


def test_default_timeout_is_applied(monkeypatch):
    seen = {}

    def fake_send(self, request, **kwargs):
        seen["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(HTTPAdapter, "send", fake_send)
    build_session(timeout=7).get_adapter("https://jobicy.com").send("request")

    assert seen["timeout"] == 7


def test_explicit_timeout_is_kept(monkeypatch):
    seen = {}

    def fake_send(self, request, **kwargs):
        seen["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(HTTPAdapter, "send", fake_send)
    build_session(timeout=7).get_adapter("https://jobicy.com").send("request", timeout=3)

    assert seen["timeout"] == 3
