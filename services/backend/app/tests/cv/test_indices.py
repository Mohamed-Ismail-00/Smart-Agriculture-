"""Vegetation indices must keep cloud-masked pixels as missing, not as bare soil."""

import numpy as np
import pytest

from app.cv import indices

NIR = np.array([0.45, np.nan, 0.50, 0.0])
RED = np.array([0.05, np.nan, 0.06, 0.0])
OTHER = np.array([0.03, np.nan, 0.03, 0.0])


@pytest.mark.parametrize(
    "values",
    [
        indices.compute_ndvi(NIR, RED),
        indices.compute_evi(NIR, RED, OTHER),
        indices.compute_ndwi(NIR, OTHER),
        indices.compute_savi(NIR, RED),
        indices.compute_gndvi(NIR, OTHER),
    ],
    ids=["ndvi", "evi", "ndwi", "savi", "gndvi"],
)
def test_masked_pixel_stays_missing(values):
    assert np.isnan(values[1])
    assert not np.isnan(values[[0, 2, 3]]).any()


def test_ndvi_values_unchanged_for_valid_pixels():
    ndvi = indices.compute_ndvi(NIR, RED)
    assert ndvi[0] == pytest.approx(0.8)
    assert ndvi[3] == 0.0  # zero reflectance in both bands is still a defined 0
