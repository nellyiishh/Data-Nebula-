from typing import Any

import pytest

import pipeline.http as http


class _Answer:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _fake_requests(monkeypatch: pytest.MonkeyPatch, answers: list[Any]) -> list[str]:
    import requests

    calls: list[str] = []

    def fake(method: str, url: str, **_: Any) -> Any:
        calls.append(url)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(requests, "request", fake)
    return calls


def test_busy_answers_are_retried_until_one_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    answers = [_Answer(502), requests.ConnectionError("reset"), _Answer(200)]
    calls = _fake_requests(monkeypatch, answers)
    waits: list[float] = []

    response = http.request_with_retry("GET", "https://x/y", waits=(1, 2, 3), sleep=waits.append)

    assert response.status_code == 200
    assert len(calls) == 3 and waits == [1, 2]


def test_the_last_busy_answer_is_returned_for_the_caller_to_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_requests(monkeypatch, [_Answer(503), _Answer(503)])

    response = http.request_with_retry("GET", "https://x", waits=(0,), sleep=lambda _: None)

    assert response.status_code == 503


def test_other_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_requests(monkeypatch, [_Answer(404)])

    response = http.request_with_retry("GET", "https://x", waits=(0, 0), sleep=lambda _: None)

    assert response.status_code == 404 and len(calls) == 1
