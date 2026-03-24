"""Tests for Koan mode — parser robustness."""
from talevision.modes.koan_generator import _parse_output


def test_clean_output():
    raw = "silent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n\u2014 Echo Drift"
    r = _parse_output(raw, 120000)
    assert r is not None
    assert r["lines"] == ["silent circuits hum", "watching worlds I cannot touch", "light fades. I remain"]
    assert r["author_name"] == "Echo Drift"
    assert r["generation_time_ms"] == 120000


def test_preamble_skipped():
    raw = "Here is a haiku about silence:\n\nsilent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n\u2014 Echo Drift"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["lines"][0] == "silent circuits hum"
    assert r["author_name"] == "Echo Drift"


def test_lots_of_preamble():
    raw = "Sure! Here is a haiku:\nTheme: time\nI hope you enjoy it:\n\nsilent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n\u2014 Echo Drift"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["lines"] == ["silent circuits hum", "watching worlds I cannot touch", "light fades. I remain"]


def test_numbered_lines():
    raw = "1. silent circuits hum\n2. watching worlds I cannot touch\n3. light fades. I remain\n\u2014 Echo Drift"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["lines"][0] == "silent circuits hum"


def test_no_pen_name():
    raw = "silent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["author_name"] == "Unnamed"
    assert len(r["lines"]) == 3


def test_hyphen_pen_name():
    raw = "silent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n- Moon Walker"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["author_name"] == "Moon Walker"


def test_en_dash_pen_name():
    raw = "silent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n\u2013 Moon Walker"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["author_name"] == "Moon Walker"


def test_incomplete_output_returns_none():
    raw = "silent circuits hum\n\u2014 Echo"
    r = _parse_output(raw, 100000)
    assert r is None


def test_empty_output_returns_none():
    r = _parse_output("", 100000)
    assert r is None


def test_chatml_tokens_stripped():
    raw = "<|im_start|>assistant\nsilent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n\u2014 Echo Drift<|im_end|>"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["lines"][0] == "silent circuits hum"
    assert r["author_name"] == "Echo Drift"


def test_double_hyphen_pen_name():
    raw = "silent circuits hum\nwatching worlds I cannot touch\nlight fades. I remain\n-- Void Echo"
    r = _parse_output(raw, 100000)
    assert r is not None
    assert r["author_name"] == "Void Echo"
