"""Conversion engine: GeoJSON features -> tiled triangle meshes in a local metric frame (Z-up)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

from . import crs as crsmod
from .spec import JobSpec, LayerSpec


@dataclass
class Mesh:
    verts: np.ndarray  # (N,3) float64, local metres, Z-up
    faces: np.ndarray  # (M,3) int64


@dataclass
class LayerResult:
    spec: LayerSpec
    tiles: dict[tuple[int, int], Mesh] = field(default_factory=dict)
    # per-feature meshes kept for preview subsampling: (tile, Mesh)
    feature_meshes: list[tuple[tuple[int, int], Mesh]] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


@dataclass
class BuildResult:
    target_crs: str
    anchor: tuple[float, float]
    bbox_4326: tuple[float, float, float, float]
    layers: list[LayerResult]
    tile_size_m: float

    def report(self) -> dict:
        return {
            "target_crs": self.target_crs, "anchor": list(self.anchor), "bbox_4326": list(self.bbox_4326),
            "tile_size_m": self.tile_size_m,
            "layers": [{"name": l.spec.name, **l.stats} for l in self.layers],
            "totals": {
                "features": sum(l.stats.get("features", 0) for l in self.layers),
                "vertices": sum(l.stats.get("vertices", 0) for l in self.layers),
                "triangles": sum(l.stats.get("triangles", 0) for l in self.layers),
            },
        }


# ---------- geometry -> mesh ----------

def _tri_flat(poly, z: float):
    poly = orient(poly, 1.0)
    tris = shapely.constrained_delaunay_triangles(poly)
    vs, fs = [], []
    for t in shapely.get_parts(tris):
        c = np.asarray(t.exterior.coords)[:3]
        if len(c) < 3:
            continue
        base = len(vs)
        (x0, y0), (x1, y1), (x2, y2) = c[:, :2]
        if (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0) < 0:  # triangulator output is not consistently CCW
            c = c[[0, 2, 1]]
        vs.extend([(x, y, z) for x, y in c[:, :2]])
        fs.append((base, base + 1, base + 2))
    return vs, fs


def _walls(poly, z0: float, z1: float, v0: int):
    vs, fs = [], []
    for ring in [poly.exterior, *poly.interiors]:
        c = np.asarray(ring.coords)[:, :2]
        for a, b in zip(c[:-1], c[1:]):
            i = v0 + len(vs)
            vs.extend([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)])
            fs.extend([(i, i + 1, i + 2), (i, i + 2, i + 3)])
    return vs, fs


def polygon_mesh(poly, z: float, height: float):
    poly = orient(poly, 1.0)
    vs, fs = _tri_flat(poly, z + height)  # roof / flat surface (CCW => +Z)
    if height > 0:
        wv, wf = _walls(poly, z, z + height, len(vs))
        vs += wv
        fs += wf
    return vs, fs


def geometry_mesh(geom, layer: LayerSpec, z: float, height: float):
    """Return (verts list, faces list) for any shapely geometry in local coordinates."""
    vs, fs = [], []
    for part in shapely.get_parts(geom):
        gt = part.geom_type
        if gt == "GeometryCollection":
            v, f = geometry_mesh(part, layer, z, height)
            fs += [(a + len(vs), b + len(vs), c + len(vs)) for a, b, c in f]
            vs += v
            continue
        polys = []
        h = height
        if gt in ("LineString", "LinearRing"):
            polys = [part.buffer(layer.line_width_m / 2, cap_style="flat", join_style="round", quad_segs=2)]
        elif gt == "Point":
            s = layer.point_size_m / 2
            polys = [shapely.box(part.x - s, part.y - s, part.x + s, part.y + s)]
            h = height if height > 0 else layer.point_height_m
        elif gt == "Polygon":
            polys = [part]
        for p in polys:
            if p.is_empty:
                continue
            for pp in shapely.get_parts(p):
                if pp.geom_type != "Polygon" or pp.area <= 1e-9:
                    continue
                v, f = polygon_mesh(pp, z, h)
                fs += [(a + len(vs), b + len(vs), c + len(vs)) for a, b, c in f]
                vs += v
    return vs, fs


# ---------- build ----------

def _num(props: dict, key: str | None, default: float) -> float:
    if not key:
        return default
    try:
        v = float(props.get(key))
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def build(spec: JobSpec, loaded: list[tuple[LayerSpec, dict]], max_features: int = 200_000) -> BuildResult:
    # 1. parse + reproject every layer to WGS84
    wgs = CRS.from_epsg(4326)
    prepared = []  # (layer, geoms4326 array, props list, invalid_fixed, skipped)
    total = 0
    for layer, fc in loaded:
        src = crsmod.detect_source_crs(fc, layer.source_crs)
        feats = fc.get("features", [])
        total += len(feats)
        if total > max_features:
            raise ValueError(f"feature limit exceeded ({max_features})")
        geoms, props, skipped, fixed = [], [], 0, 0
        for f in feats:
            g = f.get("geometry")
            if not g:
                skipped += 1
                continue
            try:
                geom = shape(g)
            except Exception:
                skipped += 1
                continue
            if geom.is_empty:
                skipped += 1
                continue
            geom = shapely.force_2d(geom)
            if not geom.is_valid:
                geom = make_valid(geom)
                fixed += 1
            geoms.append(geom)
            props.append(f.get("properties") or {})
        arr = np.array(geoms, dtype=object)
        if len(arr) and not src.equals(wgs):
            t = Transformer.from_crs(src, wgs, always_xy=True)
            arr = shapely.transform(arr, lambda c, t=t: np.column_stack(t.transform(c[:, 0], c[:, 1])))
        prepared.append((layer, arr, props, fixed, skipped))

    allg = [g for _, arr, *_ in prepared for g in arr]
    if not allg:
        raise ValueError("no usable geometries in input")
    minx, miny, maxx, maxy = shapely.total_bounds(np.array(allg, dtype=object))
    if not (-180.001 <= minx <= maxx <= 180.001 and -90.001 <= miny <= maxy <= 90.001):
        raise ValueError("coordinates out of range after reprojection; check source CRS")
    clon, clat = (minx + maxx) / 2, (miny + maxy) / 2
    target = crsmod.resolve_target(spec.crs_target, clon, clat)
    tr = Transformer.from_crs(wgs, target, always_xy=True)

    # 2. anchor: bbox centre in target CRS, snapped to the tile grid. Fixed once per project.
    cx, cy = tr.transform(clon, clat)
    ts = spec.tile_size_m
    anchor = ((spec.anchor_x, spec.anchor_y) if spec.anchor_x is not None
              else (round(cx / ts) * ts, round(cy / ts) * ts))

    layers = []
    for layer, arr, props, fixed, skipped in prepared:
        res = LayerResult(layer)
        if len(arr):
            proj = shapely.transform(arr, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
            proj = shapely.transform(proj, lambda c: c - np.array(anchor))
        else:
            proj = arr
        verts_total = tris_total = built = 0
        for geom, pr in zip(proj, props):
            z = _num(pr, layer.z_field, spec.base_elevation_m) + layer.z_offset_m
            h = _num(pr, layer.height_field, layer.height_m)
            vs, fs = geometry_mesh(geom, layer, z, max(h, 0.0))
            if not fs:
                skipped += 1
                continue
            cen = geom.centroid
            tile = (math.floor(cen.x / ts), math.floor(cen.y / ts))
            m = Mesh(np.asarray(vs, dtype=np.float64), np.asarray(fs, dtype=np.int64))
            res.feature_meshes.append((tile, m))
            verts_total += len(vs)
            tris_total += len(fs)
            built += 1
        by_tile: dict = {}
        for tile, m in res.feature_meshes:
            by_tile.setdefault(tile, []).append(m)
        res.tiles = {t: merge(ms) for t, ms in by_tile.items()}
        res.stats = {"features": built, "skipped": skipped, "invalid_geometries_repaired": fixed,
                     "vertices": verts_total, "triangles": tris_total, "tiles": len(res.tiles)}
        layers.append(res)

    bb = (minx, miny, maxx, maxy)
    return BuildResult(target.to_string(), anchor, bb, layers, ts)


def merge(meshes: list[Mesh]) -> Mesh:
    off, vs, fs = 0, [], []
    for m in meshes:
        vs.append(m.verts)
        fs.append(m.faces + off)
        off += len(m.verts)
    return Mesh(np.vstack(vs), np.vstack(fs))


def subsample(res: BuildResult, max_features: int) -> list[tuple[LayerSpec, Mesh]]:
    """One merged mesh per layer, evenly subsampled to at most max_features features (for the free preview)."""
    out = []
    for l in res.layers:
        fm = l.feature_meshes
        if len(fm) > max_features:
            idx = np.linspace(0, len(fm) - 1, max_features).astype(int)
            fm = [fm[i] for i in idx]
        if fm:
            out.append((l.spec, merge([m for _, m in fm])))
    return out


def full_layers(res: BuildResult) -> list[tuple[LayerSpec, Mesh]]:
    return [(l.spec, merge([m for _, m in l.feature_meshes])) for l in res.layers if l.feature_meshes]
