"""Smart defaults derived from the data itself, so users rarely need to touch parameters."""
import math
import re

HEIGHT = ["height", "heights", "yukseklik", "yükseklik", "bina_yuksekligi", "building_height", "bldg_height", "bina_yuk",
          "h", "hgt", "ht", "roof_height", "yukseklik_m"]
FLOORS = ["floors", "floor", "kat", "kat_sayisi", "katsayisi", "levels", "building_levels", "building:levels", "storeys",
          "stories", "num_floors", "kat_adedi"]
ELEV = ["z", "elev", "elevation", "kot", "altitude", "alt", "zkot", "z_value"]
WIDTH = ["width", "genislik", "genişlik", "en", "yol_genisligi", "road_width", "w"]
COLORS = [(r"road|yol|street|cadde|sokak|highway|rail|hat\b|line|kanal|boru|pipe", "#7b8794"),
          (r"build|bina|yapi|konut|house|ev\b|footprint", "#d4c4a8"),
          (r"tree|agac|ağaç|green|yesil|yeşil|park|orman|forest|veg", "#3fa34d"),
          (r"water|su\b|river|dere|nehir|lake|göl|gol|deniz|sea", "#5b9bd5")]
BY_GEOM = {"line": "#9aa5b1", "polygon": "#c98a5b", "point": "#e0b84c"}


def _match(fields: list[dict], names: list[str], numeric_only=True):
    low = {f["name"].lower(): f for f in fields}
    for n in names:
        f = low.get(n)
        if f and (f["numeric"] or not numeric_only):
            return f["name"]
    return None


def suggest(name: str, geometry: str | None, fields: list[dict]) -> dict:
    """fields: [{name, numeric}]. Returns defaults for the layer."""
    color = BY_GEOM.get(geometry or "", "#9aa5b1")
    for pat, c in COLORS:
        if re.search(pat, name.lower()):
            color = c
            break
    out = {"color": color, "height_field": None, "height_scale": 1.0, "z_field": None, "width_field": None,
           "width_m": 6.0, "height_m": 0.0, "point_size_m": 2.0, "point_height_m": 6.0}
    hf = _match(fields, HEIGHT)
    if hf:
        out["height_field"] = hf
    else:
        fl = _match(fields, FLOORS)
        if fl:
            out["height_field"], out["height_scale"] = fl, 3.0
    if geometry == "polygon" and not out["height_field"] and re.search(COLORS[1][0], name.lower()):
        out["height_m"] = 10.0
    out["z_field"] = _match(fields, ELEV)
    out["width_field"] = _match(fields, WIDTH) if geometry == "line" else None
    return out


def nice_tile(extent_m: float) -> int:
    """Pick a tile size giving roughly 4-12 tiles across the data."""
    target = max(extent_m / 8.0, 1.0)
    for t in (100, 250, 500, 1000, 2000, 5000):
        if t >= target:
            return t
    return 5000


def extent_m(bbox4326) -> float:
    minx, miny, maxx, maxy = bbox4326
    lat = (miny + maxy) / 2
    return max((maxx - minx) * 111_320 * math.cos(math.radians(lat)), (maxy - miny) * 111_320)
