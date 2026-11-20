"""Data acquisition: uploads, GeoJSON URL, ArcGIS REST, GeoServer/OGC WFS, built-in demo."""
import base64
import json
import math

from . import ssrf
from .config import Settings
from .spec import LayerSpec


class SourceError(ValueError):
    pass


def _parse(raw: bytes) -> dict:
    try:
        fc = json.loads(raw.decode("utf-8-sig"))
    except Exception as e:
        raise SourceError("data is not valid GeoJSON/JSON") from e
    return normalize(fc)


def normalize(fc: dict) -> dict:
    t = fc.get("type")
    if t == "FeatureCollection":
        return fc
    if t == "Feature":
        return {"type": "FeatureCollection", "features": [fc]}
    if t in ("Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection"):
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": fc, "properties": {}}]}
    raise SourceError("not a GeoJSON FeatureCollection")


def load_layer(layer: LayerSpec, uploads: dict[str, bytes], cfg: Settings) -> dict:
    hdrs = {}
    if layer.source in ("wfs", "geojson_url"):
        if layer.username and layer.password:
            hdrs["Authorization"] = "Basic " + base64.b64encode(f"{layer.username}:{layer.password}".encode()).decode()
        elif layer.token:
            hdrs["Authorization"] = "Bearer " + layer.token
    fetch = lambda url, params=None, data=None, headers=None: ssrf.safe_get(  # noqa: E731
        url, params=params, data=data, headers={**hdrs, **(headers or {})}, timeout=cfg.fetch_timeout_s,
        max_bytes=cfg.max_upload_mb * 1024 * 1024, allow_private=cfg.allow_private_hosts,
        verify=cfg.ca_bundle or True)
    try:
        if layer.source == "upload":
            if layer.file not in uploads:
                raise SourceError(f"uploaded file not found: {layer.file}")
            return _parse(uploads[layer.file])
        if layer.source == "demo":
            return demo_data(layer.url or "roads")
        if not layer.url:
            raise SourceError("url required")
        if layer.source == "geojson_url":
            return _parse(fetch(layer.url))
        if layer.source == "arcgis":
            return _arcgis(layer, fetch, cfg)
        if layer.source == "wfs":
            return _wfs(layer, fetch, cfg)
    except ssrf.UnsafeURL as e:
        raise SourceError(f"{layer.name}: {e}") from e
    raise SourceError("unknown source")


def _arcgis(layer, fetch, cfg):
    base = layer.url.rstrip("/").split("?")[0]
    if not base.endswith("/query"):
        base += "/query"
    token = layer.token or (_arcgis_token(layer, fetch) if layer.username and layer.password else None)
    feats, offset, page = [], 0, 1000
    while True:
        q = {"where": layer.where, "outFields": "*", "outSR": 4326, "f": "geojson",
             "resultOffset": offset, "resultRecordCount": page}
        if token:
            q["token"] = token
        fc = _parse_arcgis(fetch(base, q))
        got = fc.get("features", [])
        feats += got
        if len(feats) > cfg.max_features:
            raise SourceError(f"{layer.name}: feature limit exceeded ({cfg.max_features})")
        # Servers may clamp the page size: keep going while they say there is more, or page was full.
        more = fc.get("exceededTransferLimit") or (fc.get("properties") or {}).get("exceededTransferLimit")
        if not got or not more:
            break
        offset += len(got)
    return {"type": "FeatureCollection", "features": feats, "crs_hint": "EPSG:4326"}


def _parse_arcgis(raw: bytes) -> dict:
    """ArcGIS reports errors as HTTP 200 + {"error": {...}}; surface them readably."""
    try:
        j = json.loads(raw.decode("utf-8-sig"))
    except Exception as e:
        raise SourceError("ArcGIS response is not JSON") from e
    if isinstance(j, dict) and "error" in j:
        e = j["error"] or {}
        code = e.get("code")
        if code in (498, 499):
            raise SourceError("ArcGIS: token required or invalid (login failed or no access)")
        raise SourceError(f"ArcGIS error {code}: {e.get('message', '')}"[:200])
    return normalize(j)


def _arcgis_token(layer, fetch) -> str:
    """Obtain a token via the server's own token service (found through /rest/info)."""
    url = layer.url
    root = url.split("/rest/services")[0] if "/rest/services" in url else url.rsplit("/", 1)[0]
    token_url = root + "/tokens/generateToken"
    try:
        info = json.loads(fetch(root + "/rest/info", {"f": "json"}))
        token_url = (info.get("authInfo") or {}).get("tokenServicesUrl") or token_url
    except Exception:
        pass
    raw = fetch(token_url, data={"username": layer.username, "password": layer.password, "client": "requestip",
                                 "expiration": 30, "f": "json"})
    j = json.loads(raw)
    if "token" not in j:
        msg = (j.get("error") or {}).get("message", "login failed")
        raise SourceError(f"ArcGIS login failed: {msg}"[:200])
    return j["token"]


def _wfs(layer, fetch, cfg):
    if not layer.type_name:
        raise SourceError("WFS needs type_name")
    base = layer.url.split("?")[0]
    feats, start, page = [], 0, 5000
    while True:
        raw = fetch(base, {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                           "typeNames": layer.type_name, "outputFormat": "application/json",
                           "srsName": "EPSG:4326", "count": page, "startIndex": start})
        got = _parse(raw).get("features", [])
        feats += got
        if len(feats) > cfg.max_features:
            raise SourceError(f"{layer.name}: feature limit exceeded ({cfg.max_features})")
        if len(got) < page:
            break
        start += len(got)
    return {"type": "FeatureCollection", "features": feats, "crs_hint": "EPSG:4326"}


def demo_data(kind: str) -> dict:
    """Synthetic city block grid around (13.40E, 52.52N). No third-party data."""
    lon0, lat0 = 13.40, 52.52
    dlat = 1 / 111_320
    dlon = dlat / math.cos(math.radians(lat0))
    feats = []

    def ll(x, y):
        return [round(lon0 + x * dlon, 7), round(lat0 + y * dlat, 7)]

    if kind == "roads":
        for i in range(-4, 5):
            feats.append(_f({"type": "LineString", "coordinates": [ll(i * 100, -450), ll(i * 100, 450)]}, {"name": f"ns{i}"}))
            feats.append(_f({"type": "LineString", "coordinates": [ll(-450, i * 100), ll(450, i * 100)]}, {"name": f"ew{i}"}))
        feats.append(_f({"type": "LineString", "coordinates": [ll(-450 + k * 45, 120 * math.sin(k / 3)) for k in range(21)]},
                        {"name": "river_road"}))
    elif kind == "buildings":
        for i in range(-4, 4):
            for j in range(-4, 4):
                x, y = i * 100 + 15, j * 100 + 15
                w, d = 55 + (i * 7 + j * 3) % 20, 55 + (i * 5 + j * 11) % 20
                ring = [ll(x, y), ll(x + w, y), ll(x + w, y + d), ll(x, y + d), ll(x, y)]
                feats.append(_f({"type": "Polygon", "coordinates": [ring]}, {"height": 8 + ((i * 13 + j * 7) % 9) * 4}))
    elif kind == "trees":
        for i in range(-4, 4):
            for j in range(-4, 4):
                feats.append(_f({"type": "Point", "coordinates": ll(i * 100 + 8, j * 100 + 8)}, {"h": 6 + (i + j) % 4}))
    else:
        raise SourceError("unknown demo layer")
    return {"type": "FeatureCollection", "features": feats}


def _f(g, p):
    return {"type": "Feature", "geometry": g, "properties": p}
