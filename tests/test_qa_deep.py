"""Unit tests for QA helper utilities."""
from scripts.qa_helpers import solve_captcha


def test_solve_captcha():
    assert solve_captcha("3 + 7") == "10"
    assert solve_captcha("12 + 5") == "17"
    assert solve_captcha("bad") == "0"
