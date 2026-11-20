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
def mk(cfg, email="a@example.com"):
    c = TestClient(create_app(cfg), headers={"X-CSRF": "1"})
    r = c.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def client(tmp_path):
    cfg = Settings(data_dir=tmp_path, preview_max_features=20)
    return mk(cfg)


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
    c = mk(cfg)
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
    c = mk(Settings(data_dir=tmp_path, stripe_secret_key="sk_test_x"))
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


# ---- authenticated sources ----
def _auth_server():
    import base64, http.server, threading, urllib.parse
    gj = json.dumps(sources.demo_data("roads")).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def _send(self, obj):
            b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
        def do_POST(self):
            body = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            if body.get("username") == ["u"] and body.get("password") == ["p"]:
                self._send({"token": "TOK123"})
            else:
                self._send({"error": {"code": 400, "message": "Invalid username or password."}})
        def do_GET(self):
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            if u.path.endswith("/rest/info"):
                return self._send({"authInfo": {"tokenServicesUrl": f"http://127.0.0.1:{self.server.server_port}/tokens/generateToken"}})
            if "/arcgis/rest/services" in u.path:
                if q.get("token") != ["TOK123"]:
                    return self._send({"error": {"code": 499, "message": "Token Required"}})
                return self._send(gj)
            if self.headers.get("Authorization") != "Basic " + base64.b64encode(b"u:p").decode():
                self.send_response(401); self.end_headers(); return
            self._send(gj)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _run(tmp_path, layer):
    import uuid
    c = mk(Settings(data_dir=tmp_path, allow_private_hosts=True), f"{uuid.uuid4().hex[:8]}@example.com")
    r = c.post("/api/jobs", data={"spec": json.dumps({"layers": [layer]})})
    return c, wait_ready(c, r.json()["id"])


def test_arcgis_login_wfs_basic_and_no_secret_leak(tmp_path):
    srv = _auth_server(); base = f"http://127.0.0.1:{srv.server_port}"
    ags = {"name": "a", "source": "arcgis", "url": f"{base}/arcgis/rest/services/X/FeatureServer/0"}
    c, j = _run(tmp_path, {**ags, "username": "u", "password": "p"})
    assert j["status"] == "ready"
    c, j = _run(tmp_path, {**ags, "token": "TOK123"})
    assert j["status"] == "ready"
    c, j = _run(tmp_path, {**ags, "username": "u", "password": "WRONG-SECRET"})
    assert j["status"] == "failed" and "WRONG-SECRET" not in json.dumps(j)
    c, j = _run(tmp_path, ags)  # no creds -> readable error
    assert j["status"] == "failed" and "token" in j["error"].lower()
    wfs = {"name": "w", "source": "geojson_url", "url": f"{base}/data.geojson"}
    assert _run(tmp_path, {**wfs, "username": "u", "password": "p"})[1]["status"] == "ready"
    c, j = _run(tmp_path, {**wfs, "username": "u", "password": "SECRET-PW"})
    assert j["status"] == "failed" and "SECRET-PW" not in json.dumps(j)
    # credentials never persisted or returned
    import sqlite3
    row = sqlite3.connect(tmp_path / "db.sqlite").execute("SELECT group_concat(spec) FROM jobs").fetchone()[0]
    assert "SECRET-PW" not in row and "WRONG-SECRET" not in row and "TOK123" not in row and '"p"' not in row
    srv.shutdown()


def test_validation_error_does_not_echo_password(tmp_path):
    c = mk(Settings(data_dir=tmp_path))
    bad = {"layers": [{"name": "a", "source": "arcgis", "url": "http://x", "password": "TOPSECRET", "color": "red"}]}
    r = c.post("/api/jobs", data={"spec": json.dumps(bad)})
    assert r.status_code == 422 and "TOPSECRET" not in r.text



# ---- accounts, sessions, ownership ----
def test_login_required_and_csrf(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    anon = TestClient(create_app(cfg), headers={"X-CSRF": "1"})
    assert anon.post("/api/jobs", data={"spec": "{}"}).status_code == 401
    assert anon.get("/api/auth/me").status_code == 401
    nocsrf = TestClient(create_app(cfg))
    assert nocsrf.post("/api/auth/signup", json={"email": "x@example.com", "password": "correct-horse-battery"}).status_code == 403


def test_signup_validation_and_login_flow(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    c = TestClient(create_app(cfg), headers={"X-CSRF": "1"})
    assert c.post("/api/auth/signup", json={"email": "bad", "password": "correct-horse-battery"}).status_code == 422
    assert c.post("/api/auth/signup", json={"email": "a@example.com", "password": "short"}).status_code == 422
    assert c.post("/api/auth/signup", json={"email": "a@example.com", "password": "correct-horse-battery"}).status_code == 200
    assert c.post("/api/auth/signup", json={"email": "A@example.com", "password": "correct-horse-battery"}).status_code == 409
    assert c.get("/api/auth/me").json() == {"email": "a@example.com", "is_admin": False}
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401
    assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).status_code == 200
    import sqlite3
    row = sqlite3.connect(tmp_path / "db.sqlite").execute("SELECT pw_hash FROM users").fetchone()[0]
    assert row.startswith("scrypt$") and "correct-horse" not in row


def test_lockout_after_5_failures(tmp_path):
    c = mk(Settings(data_dir=tmp_path))
    c.post("/api/auth/logout")
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope-nope"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 429  # even the right password is refused while locked


def test_tenant_isolation_and_admin(tmp_path):
    cfg = Settings(data_dir=tmp_path, admin_emails="boss@example.com")
    app = create_app(cfg)
    def client(email):
        c = TestClient(app, headers={"X-CSRF": "1"})
        assert c.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"}).status_code == 200
        return c
    a, b, boss = client("a@example.com"), client("b@example.com"), client("boss@example.com")
    jid = a.post("/api/jobs", data={"spec": json.dumps(demo_spec().model_dump())}).json()["id"]
    wait_ready(a, jid)
    a.post(f"/api/jobs/{jid}/mock-pay")
    for path in ("", "/preview.glb", "/download"):          # B cannot touch A's job in any way
        assert b.get(f"/api/jobs/{jid}{path}").status_code == 404
    assert b.post(f"/api/jobs/{jid}/mock-pay").status_code == 404
    assert b.get("/api/my/jobs").json() == []
    assert len(a.get("/api/my/jobs").json()) == 1
    assert a.get("/api/admin/overview").status_code == 403 and b.get("/api/admin/overview").status_code == 403
    ov = boss.get("/api/admin/overview").json()             # admin sees users, live sessions and jobs
    assert {u["email"] for u in ov["users"]} == {"a@example.com", "b@example.com", "boss@example.com"}
    assert {s["email"] for s in ov["sessions"]} >= {"a@example.com", "b@example.com"}
    assert ov["jobs"][0]["email"] == "a@example.com"
    assert "pw_hash" not in json.dumps(ov) and "token" not in json.dumps(ov["sessions"])
    assert boss.get(f"/api/jobs/{jid}/download").status_code == 200   # admin can open any job


# ---- saved services / catalog ----
def _svc_server():
    import http.server, threading, urllib.parse
    gj = json.dumps(sources.demo_data("roads")).encode()
    me = {}

    class H(http.server.BaseHTTPRequestHandler):
        def _send(self, obj, ctype="application/json"):
            b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            P = u.path
            if P == "/arcgis/rest/services":
                return self._send({"folders": ["Open", "Secret"], "services": [{"name": "Root", "type": "FeatureServer"}]})
            if P == "/arcgis/rest/services/Open":
                return self._send({"services": [{"name": "Open/Roads", "type": "FeatureServer"}, {"name": "Open/Img", "type": "ImageServer"}]})
            if P == "/arcgis/rest/services/Secret":
                return self._send({"error": {"code": 403, "message": "forbidden"}})
            if P.endswith("/FeatureServer"):
                return self._send({"layers": [{"id": 0, "name": "Streets"}, {"id": 3, "name": "Parcels"}]})
            if P.endswith("/FeatureServer/0/query"):
                return self._send({"count": 1234})
            if P.endswith("/FeatureServer/0"):
                return self._send({"name": "Streets", "geometryType": "esriGeometryPolyline",
                                   "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}, {"name": "NAME", "type": "esriFieldTypeString"}]})
            if q.get("request") == ["GetCapabilities"]:
                return self._send(b'<WFS_Capabilities><FeatureTypeList><FeatureType><Name>ws:roads</Name><Title>Road centrelines</Title></FeatureType>'
                                  b'<FeatureType><Name>ws:poi</Name><Title></Title></FeatureType></FeatureTypeList></WFS_Capabilities>', "text/xml")
            if q.get("resultType") == ["hits"]:
                return self._send(b'<wfs:FeatureCollection numberMatched="77" numberReturned="0"/>', "text/xml")
            if q.get("request") == ["GetFeature"]:
                return self._send(gj)
            self._send(gj)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_connections_catalog_info(tmp_path):
    srv = _svc_server(); base = f"http://127.0.0.1:{srv.server_port}"
    app = create_app(Settings(data_dir=tmp_path, allow_private_hosts=True))
    def cl(email):
        c = TestClient(app, headers={"X-CSRF": "1"})
        c.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"}); return c
    a, b = cl("a@example.com"), cl("b@example.com")
    ags = a.post("/api/connections", json={"name": "City GIS", "kind": "arcgis", "url": f"{base}/arcgis/rest/services"}).json()
    r = a.post(f"/api/connections/{ags['id']}/catalog", json={}).json()["layers"]
    names = {(l["group"], l["name"]) for l in r}
    assert ("Open/Roads", "Streets") in names and ("Root", "Parcels") in names       # folder + root services, Secret skipped, ImageServer ignored
    assert not any(l["group"] == "Open/Img" for l in r)
    info = a.post(f"/api/connections/{ags['id']}/info", json={"ref": f"{base}/arcgis/rest/services/Open/Roads/FeatureServer/0"}).json()
    assert info["count"] == 1234 and info["geometry"] == "line" and info["fields"][1]["name"] == "NAME"
    w = a.post("/api/connections", json={"name": "GeoServer", "kind": "wfs", "url": f"{base}/geoserver/ows"}).json()
    lay = a.post(f"/api/connections/{w['id']}/catalog", json={}).json()["layers"]
    assert [l["ref"] for l in lay] == ["ws:roads", "ws:poi"] and lay[0]["name"] == "Road centrelines" and lay[1]["name"] == "ws:poi"
    wi = a.post(f"/api/connections/{w['id']}/info", json={"ref": "ws:roads"}).json()
    assert wi["count"] == 77 and wi["geometry"] == "line"
    # ownership; credentials never persisted; bad input
    assert b.get("/api/connections").json() == []
    assert b.post(f"/api/connections/{ags['id']}/catalog", json={}).status_code == 404
    a.post(f"/api/connections/{ags['id']}/catalog", json={"username": "u", "password": "SECRET-PW"})
    import sqlite3
    dump = str(sqlite3.connect(tmp_path / "db.sqlite").execute("SELECT * FROM connections").fetchall())
    assert "SECRET-PW" not in dump
    assert a.post("/api/connections", json={"name": "x", "kind": "ftp", "url": "http://x.com"}).status_code == 422
    bad = TestClient(create_app(Settings(data_dir=tmp_path / "x")), headers={"X-CSRF": "1"})
    bad.post("/api/auth/signup", json={"email": "c@example.com", "password": "correct-horse-battery"})
    assert bad.post("/api/connections", json={"name": "x", "kind": "arcgis", "url": "http://169.254.169.254/"}).status_code == 422
    assert a.delete(f"/api/connections/{w['id']}").status_code == 200 and len(a.get("/api/connections").json()) == 1
    srv.shutdown()


# ---- inspect / smart defaults ----
def test_suggest_rules():
    from usdconv import suggest as sg
    f = lambda *n: [{"name": x, "numeric": True} for x in n]  # noqa: E731
    s = sg.suggest("binalar", "polygon", f("OBJECTID", "Height"))
    assert s["height_field"] == "Height" and s["height_scale"] == 1.0 and s["color"] == "#d4c4a8"
    s = sg.suggest("x", "polygon", f("kat"))
    assert s["height_field"] == "kat" and s["height_scale"] == 3.0
    assert sg.suggest("bina", "polygon", f("id"))["height_m"] == 10.0     # building-like name, no field -> sensible fixed height
    assert sg.suggest("yollar", "line", f("genislik"))["width_field"] == "genislik"
    assert sg.suggest("ağaçlar", "point", [])["color"] == "#3fa34d"
    assert sg.nice_tile(900) == 250 and sg.nice_tile(100) == 100 and sg.nice_tile(1e6) == 5000


def test_inspect_endpoint(tmp_path):
    c = mk(Settings(data_dir=tmp_path))
    def up(data, name="binalar.geojson", crs=""):
        return c.post("/api/inspect", files={"file": (name, data)}, data={"source_crs": crs})
    b = sources.demo_data("buildings")
    r = up(json.dumps(b)).json()
    assert r["geometry"] == "polygon" and r["count"] == 64 and r["crs"] == "EPSG:4326"
    assert r["suggest"]["height_field"] == "height" and r["suggested_tile_m"] in (100, 250, 500) and any(f["name"] == "height" and f["numeric"] for f in r["fields"])
    # projected numbers without CRS -> asks for it instead of guessing; then works with an override
    proj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"h": 5}, "geometry": {"type": "Point", "coordinates": [390000, 5819000]}}]}
    r = up(json.dumps(proj), "p.geojson").json()
    assert r["needs_crs"] is True
    r = up(json.dumps(proj), "p.geojson", "EPSG:32633").json()
    assert r["needs_crs"] is False and r["geometry"] == "point" and abs(r["bbox4326"][0] - 13.4) < 0.5
    assert up(b"not json").status_code == 400
    assert TestClient(c.app).post("/api/inspect", files={"file": ("x", b"{}")}, headers={"X-CSRF": "1"}).status_code == 401


def test_height_scale_and_width_field():
    spec = JobSpec(layers=[LayerSpec(name="b", source="upload", file="b.json", height_field="kat", height_scale=3.0)])
    sq = lambda x: {"type": "Polygon", "coordinates": [[[13.4 + x, 52.5], [13.4005 + x, 52.5], [13.4005 + x, 52.5005], [13.4 + x, 52.5005], [13.4 + x, 52.5]]]}  # noqa: E731
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"kat": 4}, "geometry": sq(0)}]}
    res = engine.build(spec, [(spec.layers[0], fc)])
    assert abs(res.layers[0].feature_meshes[0][1].verts[:, 2].max() - 12.1) < 0.01   # 4 floors * 3 m + 0.1 z offset
    spec = JobSpec(layers=[LayerSpec(name="r", source="upload", file="r.json", width_field="w")])
    ln = lambda w: {"type": "Feature", "properties": {"w": w}, "geometry": {"type": "LineString", "coordinates": [[13.4, 52.5], [13.401, 52.5]]}}  # noqa: E731
    res = engine.build(spec, [(spec.layers[0], {"type": "FeatureCollection", "features": [ln(4), ln(20)]})])
    ys = [m.verts[:, 1].max() - m.verts[:, 1].min() for _, m in res.layers[0].feature_meshes]
    assert ys[1] > 3 * ys[0]


def test_reset_password_cli(tmp_path, monkeypatch):
    from usdconv import admin_cli
    cfg = Settings(data_dir=tmp_path)
    c = mk(cfg)                                   # signs up a@example.com (logged in)
    c2 = TestClient(c.app, headers={"X-CSRF": "1"})
    for _ in range(5):                            # lock the account
        c2.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-wrong-wrong"})
    assert c2.post("/api/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).status_code == 429
    pws = iter(["brand-new-password", "brand-new-password"])
    monkeypatch.setattr("getpass.getpass", lambda *_: next(pws))
    assert admin_cli.main(["reset-password", "A@example.com", "--data-dir", str(tmp_path)]) == 0
    assert c.get("/api/auth/me").status_code == 401                      # old session signed out
    assert c2.post("/api/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).status_code == 401
    assert c2.post("/api/auth/login", json={"email": "a@example.com", "password": "brand-new-password"}).status_code == 200
    monkeypatch.setattr("getpass.getpass", lambda *_: "short")
    assert admin_cli.main(["reset-password", "a@example.com", "--data-dir", str(tmp_path)]) == 1
    assert admin_cli.main(["reset-password", "nobody@example.com", "--data-dir", str(tmp_path)]) == 1
    assert admin_cli.main(["reset-password", "a@example.com", "--data-dir", str(tmp_path / "nope")]) == 2


def test_static_is_not_cached(tmp_path):
    c = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert c.get("/app.js").headers["cache-control"] == "no-cache"
    assert "wiz" in c.get("/").text and 'id="stepper"' in c.get("/").text   # wizard UI is what gets served


# ---- real HTTPS (pinned IP + SNI + CA verification), timeouts, readable errors ----
def _make_certs(d):
    import shutil, subprocess
    if not shutil.which("openssl"):
        pytest.skip("openssl not available")
    run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)  # noqa: E731
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.crt", "-days", "2", "-subj", "/CN=test-ca",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "srv.key", "-out", "srv.csr", "-subj", "/CN=localhost")
    (d / "ext.cnf").write_text("subjectAltName=DNS:localhost\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth")
    run("openssl", "x509", "-req", "-in", "srv.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial", "-out", "srv.crt", "-days", "2", "-extfile", "ext.cnf")


def _https_server(d, delay=0.0):
    import http.server, ssl, threading, time as _t

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            _t.sleep(delay)
            b = (b'<WFS_Capabilities><FeatureTypeList><FeatureType><Name>epos:quakes</Name><Title>Earthquakes</Title></FeatureType>'
                 b'</FeatureTypeList></WFS_Capabilities>')
            self.send_response(200); self.send_header("Content-Type", "text/xml"); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(d / "srv.crt", d / "srv.key")
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_https_catalog_with_ca_and_errors(tmp_path):
    _make_certs(tmp_path)
    srv = _https_server(tmp_path); url = f"https://localhost:{srv.server_port}/geoserver/ows"
    def run(cfg_kw, u=url):
        c = mk(Settings(data_dir=tmp_path / cfg_kw.pop("sub"), allow_private_hosts=True, **cfg_kw))
        cid = c.post("/api/connections", json={"name": "x", "kind": "wfs", "url": u}).json()["id"]
        return c.post(f"/api/connections/{cid}/catalog", json={})
    ok = run({"sub": "a", "ca_bundle": str(tmp_path / "ca.crt")})
    assert ok.status_code == 200 and ok.json()["layers"][0]["name"] == "Earthquakes"       # verified TLS through the pinned IP
    bad = run({"sub": "b"})                                                                 # CA not trusted -> readable message, not a hang/500
    assert bad.status_code == 400 and "certificate" in bad.json()["error"].lower()
    srv.shutdown()
    slow = _https_server(tmp_path, delay=3)
    r = run({"sub": "c", "ca_bundle": str(tmp_path / "ca.crt"), "fetch_timeout_s": 1}, f"https://localhost:{slow.server_port}/ows")
    assert r.status_code == 400 and "timeout" in r.json()["error"].lower()
    slow.shutdown()
    r = run({"sub": "d"}, "http://127.0.0.1:1/ows")                                          # connection refused
    assert r.status_code == 400 and "connect" in r.json()["error"].lower()


# ---- robustness: malformed input must never produce a bare 500 or a stuck job ----
WEIRD = [b"{}", b"[]", b"null", b"5", b'{"type":"FeatureCollection","features":[null,5,"x"]}',
         b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[]},"properties":null}]}',
         b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":["a","b"]},"properties":[]}]}',
         b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"GeometryCollection","geometries":[]},"properties":{}}]}',
         b'{"type":"FeatureCollection","crs":null,"features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[1,1]},"properties":{}}]}',
         b'{"type":"FeatureCollection","crs":{"type":"name","properties":null},"features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[1,1]},"properties":{}}]}',
         b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[]},"properties":{"a":{"b":1}}}]}',
         b'{"type":"FeatureCollection","features":"nope"}', b"\xff\xfe", b""]


def test_malformed_inputs_never_500(tmp_path):
    c = TestClient(create_app(Settings(data_dir=tmp_path)), headers={"X-CSRF": "1"}, raise_server_exceptions=False)
    c.post("/api/auth/signup", json={"email": "a@example.com", "password": "correct-horse-battery"})
    for w in WEIRD:
        for crs_ in ("", "EPSG:99999", "EPSG:3857"):
            r = c.post("/api/inspect", files={"file": ("a.geojson", w)}, data={"source_crs": crs_})
            assert r.status_code < 500 and "error" in r.json() or r.status_code == 200, (w, crs_, r.text)
        spec = {"layers": [{"name": "a", "source": "upload", "file": "a.geojson"}]}
        jid = c.post("/api/jobs", data={"spec": json.dumps(spec)}, files=[("files", ("a.geojson", w))]).json()["id"]
        j = wait_ready(c, jid)
        assert j["status"] in ("ready", "failed")
        if j["status"] == "failed":
            assert "Traceback" not in j["error"] and "object has no attribute" not in j["error"], (w, j["error"])
    for raw in (b"notjson", b"[1]", b"null", b'"x"'):
        for path in ("/api/auth/login", "/api/auth/signup", "/api/connections"):
            assert c.post(path, content=raw, headers={"X-CSRF": "1"}).status_code == 422, (path, raw)
    assert c.post("/api/auth/signup", json={"email": 5, "password": None}).status_code == 422
    assert c.post("/api/connections", json={"name": "x", "kind": "wfs", "url": None}).status_code == 422
    r = c.post("/api/jobs", data={"spec": "{}"})                      # error bodies are always JSON
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/json")
