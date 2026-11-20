import json
import struct
import time

import pytest
from fastapi.testclient import TestClient

from usdconv import crs, engine, sources, ssrf, writers
from usdconv.app import create_app
from usdconv.config import Settings
from usdconv.spec import JobSpec, LayerSpec


# ---- SSRF ----
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data", "http://localhost/", "http://127.0.0.1:80/", "http://10.1.2.3/",
    "http://[::1]/", "http://127.1/", "http://2130706433/", "http://0177.0.0.1/", "http://0x7f.1/",
    "file:///etc/passwd", "ftp://example.com/", "http://example.com:22/", "http://user:pw@example.com/"])
def test_ssrf_blocks(url):
    with pytest.raises(ssrf.UnsafeURL):
        ssrf.resolve_safe(url)


def test_ssrf_redirect_to_internal(monkeypatch):
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/")
            self.end_headers()
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # first hop is allowed (test flag) but the redirect target must be re-validated.
    real = ssrf.resolve_safe
    calls = []
    def fake(url, allow_private=False, ports=(80, 443)):
        calls.append(url)
        return real(url, allow_private=("127.0.0.1" in url), ports=ports)
    monkeypatch.setattr(ssrf, "resolve_safe", fake)
    with pytest.raises(ssrf.UnsafeURL):
        ssrf.safe_get(f"http://127.0.0.1:{srv.server_port}/")
    assert any("169.254" in c for c in calls)
    srv.shutdown()


# ---- CRS ----
def test_auto_utm():
    assert crs.auto_utm(13.4, 52.5).to_epsg() == 32633
    assert crs.auto_utm(-70, -33).to_epsg() == 32719


def test_projected_without_crs_rejected():
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
          "geometry": {"type": "Point", "coordinates": [500000, 4000000]}}]}
    with pytest.raises(crs.CRSError):
        crs.detect_source_crs(fc, None)
    assert crs.detect_source_crs(fc, "EPSG:32633").to_epsg() == 32633


# ---- engine ----
def demo_spec(**kw):
    return JobSpec(name="t", layers=[
        LayerSpec(name="roads", source="demo", url="roads", line_width_m=8),
        LayerSpec(name="buildings", source="demo", url="buildings", height_field="height", color="#c0c0c0"),
        LayerSpec(name="trees", source="demo", url="trees"),
    ], **kw)


def test_engine_demo():
    spec = demo_spec()
    loaded = [(l, sources.demo_data(l.url)) for l in spec.layers]
    res = engine.build(spec, loaded)
    assert res.target_crs == "EPSG:32633"
    assert res.anchor[0] % 1000 == 0
    rep = res.report()
    assert rep["totals"]["triangles"] > 500
    # local coords near origin, buildings extruded to their height field
    b = res.layers[1]
    allv = engine.merge([m for _, m in b.feature_meshes]).verts
    assert abs(allv[:, 0]).max() < 1500 and allv[:, 2].max() > 8
    # winding: every roof/flat triangle normal points up (+Z) for the road layer
    import numpy as np
    m = engine.merge([m for _, m in res.layers[0].feature_meshes])
    a, b_, c = (m.verts[m.faces[:, i]] for i in range(3))
    nz = np.cross(b_ - a, c - a)[:, 2]
    assert (nz > 0).all()


def test_epsg_override_and_polygon_with_hole():
    spec = JobSpec(layers=[LayerSpec(name="p", source="upload", file="p.json", height_m=10)], crs_target="EPSG:3857")
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {
        "type": "Polygon", "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]],
                                            [[30, 30], [30, 60], [60, 60], [60, 30], [30, 30]]]}}]}
    fc["crs"] = {"type": "name", "properties": {"name": "EPSG:32633"}}
    res = engine.build(spec, [(spec.layers[0], fc)])
    assert res.target_crs == "EPSG:3857"
    assert res.report()["totals"]["triangles"] > 10


def test_invalid_geometry_repaired():
    spec = JobSpec(layers=[LayerSpec(name="p", source="upload", file="p.json")])
    bow = {"type": "Polygon", "coordinates": [[[13, 52], [13.001, 52.001], [13.001, 52], [13, 52.001], [13, 52]]]}
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": bow}]}
    res = engine.build(spec, [(spec.layers[0], fc)])
    assert res.layers[0].stats["invalid_geometries_repaired"] == 1


# ---- writers ----
def test_glb_valid():
    spec = demo_spec()
    res = engine.build(spec, [(l, sources.demo_data(l.url)) for l in spec.layers])
    glb = writers.write_glb(engine.full_layers(res))
    magic, ver, length = struct.unpack("<III", glb[:12])
    assert magic == 0x46546C67 and ver == 2 and length == len(glb)
    jl = struct.unpack("<I", glb[12:16])[0]
    g = json.loads(glb[20:20 + jl])
    assert len(g["meshes"]) == 3


def test_usda_structure():
    spec = demo_spec()
    res = engine.build(spec, [(l, sources.demo_data(l.url)) for l in spec.layers])
    files = writers.write_usd(res, "t")
    scene = files["scene.usda"].decode()
    assert scene.startswith("#usda 1.0") and 'upAxis = "Z"' in scene and "payload = @./tiles/" in scene
    tiles = [k for k in files if k.startswith("tiles/")]
    assert tiles and all(files[k].startswith(b"#usda 1.0") for k in tiles)
    for k in tiles:  # every payload referenced exists
        assert f"@./{k}@" in scene


def test_usd_loads_with_pxr_if_available(tmp_path):
    Usd = pytest.importorskip("pxr.Usd")
    spec = demo_spec()
    res = engine.build(spec, [(l, sources.demo_data(l.url)) for l in spec.layers])
    for k, v in writers.write_usd(res, "t").items():
        p = tmp_path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(v)
    stage = Usd.Stage.Open(str(tmp_path / "scene.usda"))
    from pxr import UsdGeom
    assert sum(1 for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)) > 0


# ---- API e2e ----
@pytest.fixture
def client(tmp_path):
    cfg = Settings(data_dir=tmp_path, preview_max_features=20)
    return TestClient(create_app(cfg))


def wait_ready(c, jid):
    for _ in range(200):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("ready", "failed"):
            return j
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_e2e_preview_pay_download(client):
    spec = demo_spec().model_dump()
    r = client.post("/api/jobs", data={"spec": json.dumps(spec)})
    jid = r.json()["id"]
    j = wait_ready(client, jid)
    assert j["status"] == "ready", j
    assert j["price_cents"] >= 900 and not j["paid"]
    assert j["report"]["preview_truncated"] is True
    assert client.get(f"/api/jobs/{jid}/preview.glb").status_code == 200
    assert client.get(f"/api/jobs/{jid}/download").status_code == 402   # not paid -> no files
    assert client.post(f"/api/jobs/{jid}/checkout").json() == {"mock": True}
    assert client.post(f"/api/jobs/{jid}/mock-pay").status_code == 200
    d = client.get(f"/api/jobs/{jid}/download")
    assert d.status_code == 200
    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(d.content))
    names = z.namelist()
    assert "scene.usda" in names and "scene.glb" in names and "report.json" in names


def test_preview_is_smaller_than_full(client, tmp_path):
    jid = client.post("/api/jobs", data={"spec": json.dumps(demo_spec().model_dump())}).json()["id"]
    wait_ready(client, jid)
    client.post(f"/api/jobs/{jid}/mock-pay")
    import io, zipfile
    full = zipfile.ZipFile(io.BytesIO(client.get(f"/api/jobs/{jid}/download").content)).read("scene.glb")
    assert len(client.get(f"/api/jobs/{jid}/preview.glb").content) < len(full)


def test_upload_and_bad_input(client):
    gj = json.dumps(sources.demo_data("roads")).encode()
    spec = JobSpec(layers=[LayerSpec(name="r", source="upload", file="roads.geojson")]).model_dump()
    r = client.post("/api/jobs", data={"spec": json.dumps(spec)}, files=[("files", ("roads.geojson", gj, "application/json"))])
    assert wait_ready(client, r.json()["id"])["status"] == "ready"
    r = client.post("/api/jobs", data={"spec": json.dumps(spec)}, files=[("files", ("roads.geojson", b"not json", "x"))])
    j = wait_ready(client, r.json()["id"])
    assert j["status"] == "failed" and "GeoJSON" in j["error"]
    assert client.post("/api/jobs", data={"spec": "{}"}).status_code == 422
    assert client.get("/api/jobs/nope/download").status_code == 404


def test_ssrf_via_api_fails_job(client):
    spec = JobSpec(layers=[LayerSpec(name="x", source="geojson_url", url="http://169.254.169.254/")]).model_dump()
    j = wait_ready(client, client.post("/api/jobs", data={"spec": json.dumps(spec)}).json()["id"])
    assert j["status"] == "failed" and "private" in j["error"]


def test_webhook_signature(tmp_path):
    import hashlib, hmac
    cfg = Settings(data_dir=tmp_path, stripe_webhook_secret="whsec_x")
    c = TestClient(create_app(cfg))
    jid = c.post("/api/jobs", data={"spec": json.dumps(demo_spec().model_dump())}).json()["id"]
    wait_ready(c, jid)
    body = json.dumps({"type": "checkout.session.completed", "data": {"object": {
        "payment_status": "paid", "client_reference_id": jid}}}).encode()
    assert c.post("/api/stripe/webhook", content=body, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
    assert c.get(f"/api/jobs/{jid}/download").status_code == 402
    ts = str(int(time.time()))
    sig = hmac.new(b"whsec_x", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert c.post("/api/stripe/webhook", content=body, headers={"stripe-signature": f"t={ts},v1={sig}"}).status_code == 200
    assert c.get(f"/api/jobs/{jid}/download").status_code == 200


def test_mock_pay_disabled_with_stripe(tmp_path):
    c = TestClient(create_app(Settings(data_dir=tmp_path, stripe_secret_key="sk_test_x")))
    jid = c.post("/api/jobs", data={"spec": json.dumps(demo_spec().model_dump())}).json()["id"]
    wait_ready(c, jid)
    assert c.post(f"/api/jobs/{jid}/mock-pay").status_code == 404


def test_wall_normals_point_outward():
    import numpy as np
    from shapely.geometry import box
    layer = LayerSpec(name="b", source="demo")
    vs, fs = engine.geometry_mesh(box(-10, -10, 10, 10), layer, 0.0, 5.0)
    v, f = np.array(vs), np.array(fs)
    a, b, c = (v[f[:, i]] for i in range(3))
    n = np.cross(b - a, c - a)
    cen = (a + b + c) / 3
    horiz = np.abs(n[:, 2]) < 1e-9
    assert horiz.sum() == 8  # 4 walls x 2 triangles
    assert (np.einsum("ij,ij->i", n[horiz][:, :2], cen[horiz][:, :2]) > 0).all()
    assert (n[~horiz][:, 2] > 0).all()  # roof faces up


def test_manual_anchor():
    spec = demo_spec(crs_target="EPSG:32633", anchor_x=390000.0, anchor_y=5819000.0)
    res = engine.build(spec, [(l, sources.demo_data(l.url)) for l in spec.layers])
    assert res.anchor == (390000.0, 5819000.0)
    with pytest.raises(Exception):
        demo_spec(anchor_x=1.0, anchor_y=2.0)            # needs explicit CRS
    with pytest.raises(Exception):
        demo_spec(crs_target="EPSG:32633", anchor_x=1.0)  # both or none
