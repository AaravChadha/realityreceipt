"""Spec §6 wording in everything `quote` writes: no em dash, no "APR", nothing about qualifying."""

import re

import pytest

from app.engine.quote import quote
from test_quote_all_paths import TERMS, FakeRepo, full_request

REQUESTS = {
    "published repair ranges, no BNPL terms": (full_request(), FakeRepo()),
    "repair quote, BNPL terms": (full_request(repair_quote_low=180.0, repair_quote_high=260.0), FakeRepo(bnpl=TERMS)),
}


@pytest.mark.parametrize("name", REQUESTS)
def test_no_label_formula_or_flag_breaks_the_copy_rules(name: str) -> None:
    req, repo = REQUESTS[name]
    paths = quote(req, repo)
    texts = [p.name for p in paths] + [f for p in paths for f in p.flags]
    texts += [t for p in paths for line in p.lines for t in (line.label, line.formula)]
    assert len(paths) == 9
    for text in texts:
        assert "\u2014" not in text, text
        assert not re.search(r"\bapr\b", text, re.IGNORECASE), text
        assert "qualif" not in text.lower(), text
