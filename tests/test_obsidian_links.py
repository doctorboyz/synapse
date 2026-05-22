"""Tests for Obsidian-style link parsing."""

import pytest

from src.ingest.obsidian_links import extract_links, replace_links


def test_extract_simple_link():
    links = extract_links("See [[Hello World]] for details.")
    assert len(links) == 1
    assert links[0]["target"] == "Hello World"
    assert links[0]["display"] is None
    assert links[0]["raw"] == "[[Hello World]]"


def test_extract_piped_link():
    links = extract_links("Go to [[Another Page|Display Text]] here.")
    assert len(links) == 1
    assert links[0]["target"] == "Another Page"
    assert links[0]["display"] == "Display Text"


def test_extract_multiple_links():
    text = "See [[A]] and [[B|bee]] plus [[C]]"
    links = extract_links(text)
    assert len(links) == 3
    assert links[0]["target"] == "A"
    assert links[1]["target"] == "B"
    assert links[2]["target"] == "C"


def test_extract_no_links():
    links = extract_links("Plain text with no links.")
    assert links == []


def test_replace_links():
    text = "See [[Hello World]] and [[Missing]]"
    resolver = {"Hello World": "abc-123"}
    result = replace_links(text, resolver)
    assert "[Hello World](/documents/abc-123)" in result
    assert "[Missing]" in result


def test_replace_piped_link():
    text = "Go to [[Target|Display]]"
    resolver = {"Target": "xyz-789"}
    result = replace_links(text, resolver)
    assert "[Display](/documents/xyz-789)" in result
