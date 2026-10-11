import pystac_client
import planetary_computer
import odc.stac
import numpy as np

bbox = [30.1, 30.1, 30.11, 30.11]
client = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

search = client.search(
    collections=["sentinel-2-l2a"],
    bbox=bbox,
    datetime="2026-05-01/2026-05-15",
    query={"eo:cloud_cover": {"lt": 20}}
)
items = list(search.items())
print(f"Found {len(items)} items")

ds = odc.stac.load(
    items,
    bbox=bbox,
    bands=["B02", "SCL"],
    crs="EPSG:4326",
    resolution=0.0001,
)

print(ds)
print("Computing...")
ds = ds.compute()
print(ds.B02.shape)
