"""CRS detection and auto-UTM selection. Principle: never silently produce wrong output."""
import math

from pyproj import CRS


class CRSError(ValueError):
    pass


def detect_source_crs(fc: dict, override: str | None) -> CRS:
    if override:
        try:
            return CRS.from_user_input(override)
        except Exception as e:
            raise CRSError(f"unknown coordinate system: {override}") from e
    crs = fc.get("crs")
    if crs:
        name = (crs.get("properties") or {}).get("name")
        if name:
            try:
                return CRS.from_user_input(name)
            except Exception as e:
                raise CRSError(f"unrecognised crs member: {name}") from e
    # RFC 7946: GeoJSON without crs member is WGS84 lon/lat. Verify the numbers agree.
    for f in fc.get("features", [])[:200]:
        g = f.get("geometry")
        if not g:
            continue
        x, y = _first_xy(g.get("coordinates") if g.get("type") != "GeometryCollection" else None)
        if x is None:
            continue
        if abs(x) > 180.0001 or abs(y) > 90.0001:
            raise CRSError("coordinates look projected but no CRS is declared; set source_crs (e.g. EPSG:3857)")
        break
    return CRS.from_epsg(4326)


def _first_xy(c):
    while isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple)):
        c = c[0]
    if isinstance(c, (list, tuple)) and len(c) >= 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in c[:2]):
        return c[0], c[1]
    return None, None


def auto_utm(lon: float, lat: float) -> CRS:
    zone = int(math.floor((lon + 180.0) / 6.0)) % 60 + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def resolve_target(spec_value: str, lon: float, lat: float) -> CRS:
    if spec_value == "auto_utm":
        return auto_utm(lon, lat)
    crs = CRS.from_user_input(spec_value)
    if not crs.is_projected:
        raise CRSError("target CRS must be projected (metres)")
    return crs
