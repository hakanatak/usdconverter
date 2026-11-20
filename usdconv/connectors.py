"""Service browsing for saved connections: catalog + layer info (ArcGIS REST, GeoServer/WFS, GeoJSON URL).
Credentials are passed per request, used in memory, and never stored."""
import json
import re
from types import SimpleNamespace
from urllib.parse import urlparse

from . import ssrf, suggest
from .config import Settings
from .sources import SourceError, _arcgis_token, _parse_arcgis

MAX_SERVICES, MAX_LAYERS = 60, 1000
GEOM = {"esriGeometryPoint": "point", "esriGeometryMultipoint": "point", "esriGeometryPolyline": "line",
        "esriGeometryPolygon": "polygon"}


def _fetcher(cfg: Settings, kind: str, user, pw, token):
    import base64
    hdrs = {}
    if kind != "arcgis":
        if user and pw:
            hdrs["Authorization"] = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
        elif token:
            hdrs["Authorization"] = "Bearer " + token

    def fetch(url, params=None, data=None):
        try:
            return ssrf.safe_get(url, params=params, data=data, headers=hdrs, timeout=cfg.fetch_timeout_s,
                                 max_bytes=20 * 1024 * 1024, allow_private=cfg.allow_private_hosts,
                                 verify=cfg.ca_bundle or True)
        except ssrf.UnsafeURL as e:
            raise SourceError(str(e)) from e
    return fetch


def _ags(cfg, url, user, pw, token):
    fetch = _fetcher(cfg, "arcgis", user, pw, token)
    tok = token or (_arcgis_token(SimpleNamespace(url=url, username=user, password=pw), fetch) if user and pw else None)

    def j(u, **q):
        q["f"] = "json"
        if tok:
            q["token"] = tok
        return _json(fetch(u.rstrip("/"), q))
    return j


def _json(raw: bytes) -> dict:
    j = _parse_arcgis_json(raw)
    return j


def _parse_arcgis_json(raw: bytes) -> dict:
    try:
        j = json.loads(raw.decode("utf-8-sig"))
    except Exception as e:
        raise SourceError("response is not JSON; is this an ArcGIS REST URL?") from e
    if isinstance(j, dict) and "error" in j:
        e = j["error"] or {}
        if e.get("code") in (498, 499):
            raise SourceError("login required or invalid (token / username / password)")
        raise SourceError(f"ArcGIS error {e.get('code')}: {e.get('message', '')}"[:200])
    return j


def catalog(cfg: Settings, kind: str, url: str, user=None, pw=None, token=None) -> list[dict]:
    if kind == "geojson_url":
        return [{"ref": url, "name": urlparse(url).path.rsplit("/", 1)[-1] or url, "group": ""}]
    if kind == "wfs":
        return _wfs_catalog(cfg, url, user, pw, token)
    if kind == "arcgis":
        return _arcgis_catalog(cfg, url, user, pw, token)
    raise SourceError("unknown connection type")


def _arcgis_catalog(cfg, url, user, pw, token):
    j = _ags(cfg, url, user, pw, token)
    url = url.split("?")[0].rstrip("/")
    info = j(url)
    out: list[dict] = []

    def from_service(svc_url, group):
        s = j(svc_url)
        for l in (s.get("layers") or []):
            out.append({"ref": f"{svc_url}/{l['id']}", "name": l.get("name", str(l["id"])), "group": group})

    if "layers" in info:                                   # a FeatureServer / MapServer
        for l in info["layers"]:
            out.append({"ref": f"{url}/{l['id']}", "name": l.get("name", str(l["id"])), "group": info.get("serviceDescription", "")[:60]})
    elif "services" in info or "folders" in info:          # services directory (root or folder)
        root = url.split("/rest/services")[0] + "/rest/services" if "/rest/services" in url else url
        pending = [(url, info)]
        for f in (info.get("folders") or [])[:30]:         # one level of folders; unreadable ones are skipped
            try:
                pending.append((f"{root}/{f}", j(f"{root}/{f}")))
            except SourceError:
                continue
        n = 0
        for _, d in pending:
            for svc in d.get("services") or []:
                if svc.get("type") not in ("FeatureServer", "MapServer") or n >= MAX_SERVICES:
                    continue
                n += 1
                try:
                    from_service(f"{root}/{svc['name']}/{svc['type']}", svc["name"])
                except SourceError:
                    continue
    elif "fields" in info or "geometryType" in info:       # a single layer
        out.append({"ref": url, "name": info.get("name", url.rsplit("/", 1)[-1]), "group": ""})
    else:
        raise SourceError("no layers found at this URL")
    return out[:MAX_LAYERS]


def _wfs_catalog(cfg, url, user, pw, token):
    fetch = _fetcher(cfg, "wfs", user, pw, token)
    raw = fetch(url.split("?")[0], {"service": "WFS", "request": "GetCapabilities"}).decode("utf-8", "replace")
    if "ExceptionReport" in raw[:2000] and "FeatureType" not in raw:
        raise SourceError("WFS returned an error (check URL / login)")
    out = []
    for blk in re.findall(r"<(?:\w+:)?FeatureType[ >](.*?)</(?:\w+:)?FeatureType>", raw, re.S)[:MAX_LAYERS]:
        n = re.search(r"<(?:\w+:)?Name>([^<]+)</", blk)
        t = re.search(r"<(?:\w+:)?Title>([^<]*)</", blk)
        if n:
            name = n.group(1).strip()
            out.append({"ref": name, "name": (t.group(1).strip() if t and t.group(1).strip() else name),
                        "group": name.split(":")[0] if ":" in name else ""})
    if not out:
        raise SourceError("no feature types found; is this a WFS endpoint?")
    return out


def layer_info(cfg: Settings, kind: str, url: str, ref: str, user=None, pw=None, token=None) -> dict:
    if kind == "arcgis":
        j = _ags(cfg, ref, user, pw, token)
        meta = j(ref)
        cnt = j(ref + "/query", where="1=1", returnCountOnly="true").get("count")
        geom = GEOM.get(meta.get("geometryType"), meta.get("geometryType"))
        flds = [{"name": f["name"], "type": f.get("type", "").replace("esriFieldType", ""),
                 "numeric": f.get("type", "") in ("esriFieldTypeInteger", "esriFieldTypeSmallInteger", "esriFieldTypeDouble",
                                                  "esriFieldTypeSingle")} for f in meta.get("fields", [])][:80]
        return {"geometry": geom, "count": cnt, "fields": flds, "suggest": suggest.suggest(meta.get("name", ""), geom, flds)}
    fetch = _fetcher(cfg, kind, user, pw, token)
    if kind == "wfs":
        base = url.split("?")[0]
        count = None
        try:
            hits = fetch(base, {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": ref,
                                "resultType": "hits"}).decode("utf-8", "replace")
            m = re.search(r'numberMatched="(\d+)"', hits) or re.search(r'numberOfFeatures="(\d+)"', hits)
            count = int(m.group(1)) if m else None
        except SourceError:
            pass
        sample = json.loads(fetch(base, {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": ref,
                                         "outputFormat": "application/json", "count": 1}))
        feats = sample.get("features") or []
    else:
        sample = json.loads(fetch(ref))
        feats = sample.get("features") or []
        count = len(feats)
        feats = feats[:1]
    f0 = feats[0] if feats else {}
    gt = ((f0.get("geometry") or {}).get("type") or "").lower()
    geom = "point" if "point" in gt else "line" if "line" in gt else "polygon" if "polygon" in gt else None
    flds = [{"name": k, "type": type(v).__name__, "numeric": isinstance(v, (int, float)) and not isinstance(v, bool)}
            for k, v in (f0.get("properties") or {}).items()][:80]
    return {"geometry": geom, "count": count, "fields": flds, "suggest": suggest.suggest(ref, geom, flds)}
