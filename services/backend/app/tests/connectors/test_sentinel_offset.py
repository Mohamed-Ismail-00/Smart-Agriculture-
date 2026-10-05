"""Sentinel-2 L2A reflectance offset (processing baseline 04.00+)."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app.connectors import sentinel


def test_offset_follows_processing_baseline():
    assert sentinel.boa_offset_dn("05.11") == 1000
    assert sentinel.boa_offset_dn("04.00") == 1000
    assert sentinel.boa_offset_dn("03.00") == 0
    # A reprocessed pre-2022 scene carries the offset even though its date is old.
    assert sentinel.boa_offset_dn("05.00", datetime(2020, 6, 1, tzinfo=timezone.utc)) == 1000


def test_offset_falls_back_to_acquisition_date():
    assert sentinel.boa_offset_dn(None, datetime(2021, 8, 1, tzinfo=timezone.utc)) == 0
    assert sentinel.boa_offset_dn(None, datetime(2024, 8, 1, tzinfo=timezone.utc)) == 1000
    assert sentinel.boa_offset_dn(None, datetime(2024, 8, 1)) == 1000  # naive = UTC


def test_ndvi_preview_expression_removes_offset():
    bbox = [31.0, 30.0, 31.05, 30.05]

    def expression(offset):
        url = sentinel._build_preview_url("sentinel-2-l2a", "ITEM", bbox, "ndvi", boa_offset=offset)
        return parse_qs(urlparse(url).query)["expression"][0]

    assert expression(1000) == "(B08-B04)/(B08+B04-2000)"
    assert expression(0) == "(B08-B04)/(B08+B04)"
