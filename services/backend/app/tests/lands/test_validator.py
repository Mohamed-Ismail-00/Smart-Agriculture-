"""Registration-time land validation: OSM zoning check must not reject fields near houses."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.lands import validator

# Wheat field near Zagazig; the nearest OSM feature is a farmhouse node ~220 m away.
FIELD_LAT, FIELD_LON = 30.631114, 31.4917895
NEARBY_HOUSE = {
    "class": "place",
    "type": "house",
    "boundingbox": ["30.6304347", "30.6305347", "31.4895214", "31.4896214"],
}


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _green_vegetation():
    with patch.object(validator.modis_ndvi, "fetch_ndvi_history", return_value=[{"ndvi_modis": 0.6}]):
        yield


def _validate(osm_payload, lat=FIELD_LAT, lon=FIELD_LON):
    with patch("httpx.Client.get", return_value=_Response(osm_payload)):
        validator.validate_agricultural_land(lat, lon)


def test_field_next_to_a_house_is_accepted():
    _validate(NEARBY_HOUSE)


def test_point_on_a_building_is_rejected():
    building = {
        "class": "building",
        "type": "yes",
        "boundingbox": ["30.6310", "30.6312", "31.4917", "31.4919"],
    }
    with pytest.raises(HTTPException) as exc:
        _validate(building)
    assert exc.value.status_code == 400


def test_point_inside_residential_area_is_rejected():
    residential = {
        "class": "landuse",
        "type": "residential",
        "boundingbox": ["30.62", "30.64", "31.48", "31.50"],
    }
    with pytest.raises(HTTPException):
        _validate(residential)


def test_urban_feature_without_bounding_box_does_not_reject():
    _validate({"class": "place", "type": "house"})
