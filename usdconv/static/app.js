import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const T = {
  tr: { tagline:'CBS verisini 3B OpenUSD\'ye dönüştür', project:'Proje', name:'Ad', crs:'Hedef koordinat sistemi', autoutm:'Otomatik UTM',
    anchor:'Referans noktası X / Y (hedef CRS, opsiyonel)', srccrs:'Kaynak CRS (opsiyonel, örn. EPSG:3857)', user:'Kullanıcı adı (opsiyonel)', pass:'Parola (opsiyonel)', tokenl:'Token (opsiyonel)', tile:'Karo boyutu (m)', base:'Taban kotu (m)', layers:'Katmanlar', addlayer:'+ Katman', demo:'Demo veri', convert:'Dönüştür ve önizle',
    result:'Sonuç', pay:'Öde ve dosyaları indir', download:'İndir (USD + GLB)', hint:'Önizleme burada görünecek',
    src_upload:'Dosya yükle (GeoJSON)', src_geojson_url:'GeoJSON URL', src_arcgis:'ArcGIS REST katmanı', src_wfs:'GeoServer / WFS',
    lname:'Katman adı', url:'URL', typename:'typeName', where:'Filtre (where)', width:'Çizgi genişliği (m)', height:'Yükseklik (m)',
    hfield:'Yükseklik alanı', zoff:'Z ofseti (m)', color:'Renk', working:'İşleniyor…', failed:'Hata: ', features:'nesne', tris:'üçgen',
    truncated:'Önizleme örneklenmiştir; teslimat tüm veriyi içerir.', paidnote:'Ödeme alındı.', mock:'(Geliştirme modu: gerçek ödeme yok)' },
  en: { tagline:'Turn GIS data into 3D OpenUSD', project:'Project', name:'Name', crs:'Target CRS', autoutm:'Auto UTM',
    anchor:'Reference point X / Y (target CRS, optional)', srccrs:'Source CRS (optional, e.g. EPSG:3857)', user:'Username (optional)', pass:'Password (optional)', tokenl:'Token (optional)', tile:'Tile size (m)', base:'Base elevation (m)', layers:'Layers', addlayer:'+ Layer', demo:'Demo data', convert:'Convert & preview',
    result:'Result', pay:'Pay & download files', download:'Download (USD + GLB)', hint:'Preview will appear here',
    src_upload:'Upload file (GeoJSON)', src_geojson_url:'GeoJSON URL', src_arcgis:'ArcGIS REST layer', src_wfs:'GeoServer / WFS',
    lname:'Layer name', url:'URL', typename:'typeName', where:'Filter (where)', width:'Line width (m)', height:'Height (m)',
    hfield:'Height field', zoff:'Z offset (m)', color:'Color', working:'Processing…', failed:'Error: ', features:'features', tris:'triangles',
    truncated:'Preview is sampled; the delivery contains all data.', paidnote:'Payment received.', mock:'(Dev mode: no real payment)' },
};
let lang = localStorage.lang || (navigator.language.startsWith('tr') ? 'tr' : 'en');
const $ = (s) => document.querySelector(s);
const t = (k) => T[lang][k] || k;
function i18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((e) => (e.textContent = t(e.dataset.i18n)));
  document.querySelectorAll('.layer [data-t]').forEach((e) => (e.firstChild.textContent = t(e.dataset.t)));
  $('#lang').textContent = lang === 'tr' ? 'EN' : 'TR';
}
$('#lang').onclick = () => { lang = lang === 'tr' ? 'en' : 'tr'; localStorage.lang = lang; i18n(); };

// ---- layers form ----
const files = {};
function addLayer(pre = {}) {
  const d = document.createElement('div');
  d.className = 'layer';
  const lab = (k, inner) => `<label data-t="${k}">${t(k)}${inner}</label>`;
  d.innerHTML = `<span class="x" title="remove">✕</span>
    ${lab('lname', '<input class="name">')}
    <label>Source<select class="src">
      <option value="upload">${t('src_upload')}</option><option value="geojson_url">${t('src_geojson_url')}</option>
      <option value="arcgis">${t('src_arcgis')}</option><option value="wfs">${t('src_wfs')}</option></select></label>
    <input class="file" type="file" accept=".geojson,.json">
    <div class="urlbox" hidden>${lab('url', '<input class="url" placeholder="https://…">')}
      <div class="auth">${lab('user', '<input class="un" autocomplete="off">')}${lab('pass', '<input class="pw" type="password" autocomplete="new-password">')}${lab('tokenl', '<input class="tk" autocomplete="off">')}</div>
      <div class="wfs" hidden>${lab('typename', '<input class="tn">')}</div>
      <div class="ags" hidden>${lab('where', '<input class="where" value="1=1">')}</div></div>
    ${lab('srccrs', '<input class="sc" placeholder="EPSG:xxxx">')}
    <div class="g">${lab('width', '<input class="w" type="number" value="6" step="0.5">')}
      ${lab('height', '<input class="h" type="number" value="0">')}
      ${lab('hfield', '<input class="hf">')}${lab('zoff', '<input class="zo" type="number" value="0.1" step="0.05">')}
      ${lab('color', '<input class="col" type="color" value="#9aa5b1">')}</div>`;
  const src = d.querySelector('.src');
  src.onchange = () => {
    const v = src.value;
    d.querySelector('.file').hidden = v !== 'upload';
    d.querySelector('.urlbox').hidden = v === 'upload';
    d.querySelector('.wfs').hidden = v !== 'wfs';
    d.querySelector('.ags').hidden = v !== 'arcgis';
  };
  d.querySelector('.x').onclick = () => d.remove();
  Object.entries(pre.v || {}).forEach(([k, v]) => (d.querySelector('.' + k).value = v));
  if (pre.demo) d.dataset.demo = pre.demo;
  if (pre.demo) { src.hidden = true; d.querySelector('.file').hidden = true; src.parentElement.hidden = true; }
  $('#layers').append(d);
  i18n();
}
$('#add').onclick = () => addLayer({ v: { name: 'layer' + ($('#layers').children.length + 1) } });
$('#demo').onclick = () => {
  $('#layers').innerHTML = '';
  addLayer({ demo: 'roads', v: { name: 'roads', w: 8, col: '#7b8794' } });
  addLayer({ demo: 'buildings', v: { name: 'buildings', hf: 'height', col: '#d4c4a8', zo: 0 } });
  addLayer({ demo: 'trees', v: { name: 'trees', col: '#3fa34d', zo: 0 } });
};

function collect() {
  const up = new FormData();
  const layers = [...document.querySelectorAll('.layer')].map((d, i) => {
    const q = (s) => d.querySelector(s);
    const L = { name: q('.name').value.trim() || 'layer' + i, line_width_m: +q('.w').value || 6, height_m: +q('.h').value || 0,
      z_offset_m: +q('.zo').value || 0, color: q('.col').value };
    if (q('.sc').value.trim()) L.source_crs = q('.sc').value.trim().toUpperCase();
    if (q('.hf').value.trim()) L.height_field = q('.hf').value.trim();
    if (d.dataset.demo) { L.source = 'demo'; L.url = d.dataset.demo; if (L.url === 'trees') { L.point_size_m = 6; L.point_height_m = 9; } return L; }
    L.source = q('.src').value;
    if (L.source === 'upload') {
      const f = q('.file').files[0];
      if (!f) throw new Error(`${L.name}: file?`);
      const fname = `${i}_${f.name}`;
      L.file = fname; up.append('files', f, fname);
    } else {
      L.url = q('.url').value.trim();
      if (q('.un').value) L.username = q('.un').value;
      if (q('.pw').value) L.password = q('.pw').value;
      if (q('.tk').value.trim()) L.token = q('.tk').value.trim();
      if (L.source === 'wfs') L.type_name = q('.tn').value.trim();
      if (L.source === 'arcgis') L.where = q('.where').value || '1=1';
    }
    return L;
  });
  const spec = { name: $('#pname').value, crs_target: $('#crs').value, tile_size_m: +$('#tile').value || 1000,
    base_elevation_m: +$('#base').value || 0, layers };
  if ($('#ax').value !== '' && $('#ay').value !== '') { spec.anchor_x = +$('#ax').value; spec.anchor_y = +$('#ay').value; }
  up.append('spec', JSON.stringify(spec));
  return up;
}

// ---- viewer ----
const view = $('#view');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
view.append(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x10141a);
const cam = new THREE.PerspectiveCamera(50, 1, 1, 100000);
const controls = new OrbitControls(cam, renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.8);
sun.position.set(300, 600, 200);
scene.add(sun);
const grid = new THREE.GridHelper(2000, 40, 0x334, 0x223);
scene.add(grid);
let model;
function resize() { const w = view.clientWidth, h = view.clientHeight; renderer.setSize(w, h); cam.aspect = w / h; cam.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, cam); })();

function showGLB(url) {
  new GLTFLoader().load(url, (g) => {
    if (model) scene.remove(model);
    model = g.scene;
    scene.add(model);
    const box = new THREE.Box3().setFromObject(model), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const r = Math.max(s.x, s.z, 50);
    cam.position.set(c.x + r * 0.8, c.y + r * 0.8, c.z + r * 0.8);
    controls.target.copy(c); controls.update();
    grid.position.set(c.x, box.min.y - 0.2, c.z);
    $('#hint').hidden = true; $('#wm').hidden = false;
  });
}

// ---- job flow ----
let job = null;
const msg = (s) => ($('#msg').textContent = s);
async function poll(id) {
  for (;;) {
    const j = await (await fetch(`/api/jobs/${id}`)).json();
    if (j.status === 'ready') return j;
    if (j.status === 'failed') throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 800));
  }
}
function render(j) {
  job = j;
  $('#result').hidden = false;
  const tot = j.report.totals;
  $('#stats').textContent = `${tot.features} ${t('features')} · ${tot.triangles} ${t('tris')} · ${j.report.target_crs}` +
    (j.report.preview_truncated ? '\n' + t('truncated') : '');
  $('#stats').style.whiteSpace = 'pre-wrap';
  $('#price').textContent = `$${(j.price_cents / 100).toFixed(2)}`;
  $('#pay').hidden = j.paid;
  $('#dl').hidden = !j.paid;
  if (j.paid) { $('#dl').href = `/api/jobs/${j.id}/download`; $('#wm').hidden = true; }
  if (j.payment_mode === 'mock' && !j.paid) msg(t('mock'));
}
async function start() {
  $('#go').disabled = true; $('#result').hidden = true;
  try {
    msg(t('working'));
    const r = await fetch('/api/jobs', { method: 'POST', body: collect() });
    const body = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(body.error));
    history.replaceState(null, '', `?job=${body.id}`);
    const j = await poll(body.id);
    msg(''); showGLB(`/api/jobs/${j.id}/preview.glb`); render(j);
  } catch (e) { msg(t('failed') + e.message); }
  $('#go').disabled = false;
}
$('#go').onclick = start;
$('#pay').onclick = async () => {
  const r = await (await fetch(`/api/jobs/${job.id}/checkout`, { method: 'POST' })).json();
  if (r.url) { location.href = r.url; return; }
  if (r.mock) await fetch(`/api/jobs/${job.id}/mock-pay`, { method: 'POST' });
  render(await (await fetch(`/api/jobs/${job.id}`)).json());
  msg(t('paidnote'));
};

// resume from ?job=
const qid = new URLSearchParams(location.search).get('job');
$('#demo').click();
if (qid) {
  fetch(`/api/jobs/${qid}/verify-payment`, { method: 'POST' }).then((r) => r.json()).then(async (j) => {
    if (j.status === 'ready') { showGLB(`/api/jobs/${qid}/preview.glb`); render(j); }
  }).catch(() => {});
}
i18n();
