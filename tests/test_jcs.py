"""Tests for the minimal JCS (RFC 8785) canonicalizer.

Spot-checks that our output matches the `serde_jcs` behavior on the
manifest types we actually serialize.
"""

from __future__ import annotations

import json

import pytest

from coproduct_a2a.jcs import canonicalize


def test_empty_object():
    assert canonicalize({}) == b"{}"


def test_empty_array():
    assert canonicalize([]) == b"[]"


def test_sorts_keys_lexicographically():
    out = canonicalize({"b": 2, "a": 1, "c": 3}).decode()
    assert out == '{"a":1,"b":2,"c":3}'


def test_no_whitespace():
    out = canonicalize({"a": [1, 2, 3]}).decode()
    assert " " not in out


def test_nested_object():
    out = canonicalize({"a": {"z": 1, "y": 2}}).decode()
    assert out == '{"a":{"y":2,"z":1}}'


def test_strings_escaped_json_compatible():
    # Embedded double-quote must be escaped.
    out = canonicalize({"msg": 'he said "hi"'}).decode()
    # round-trip via json parser to verify escaping is valid JSON.
    assert json.loads(out) == {"msg": 'he said "hi"'}


def test_booleans_and_null():
    assert canonicalize(True) == b"true"
    assert canonicalize(False) == b"false"
    assert canonicalize(None) == b"null"


def test_integer_no_leading_zero():
    assert canonicalize(0) == b"0"
    assert canonicalize(123) == b"123"
    assert canonicalize(-5) == b"-5"


def test_deterministic_across_calls():
    obj = {"b": 2, "a": [3, {"y": 9, "x": 8}], "c": "z"}
    first = canonicalize(obj)
    second = canonicalize(obj)
    assert first == second


def test_floats_rejected():
    with pytest.raises(ValueError):
        canonicalize({"n": 1.5})
