import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/* ---------- i18n ---------- */
const T = {
  tr: { tagline: 'CBS verisini 3B OpenUSD\'ye dönüştür', nav_new: 'Dönüşüm', nav_sources: 'Kaynaklar', nav_jobs: 'İşlerim',
    email: 'E-posta', password: 'Parola (en az 10 karakter)', login: 'Giriş yap', signup: 'Hesap oluştur', logout: 'Çıkış',
    project: 'Proje', name: 'Ad', crs: 'Hedef CRS', autoutm: 'Otomatik UTM', tile: 'Karo (m)', base: 'Taban kotu (m)',
    anchor: 'Referans noktası X / Y (opsiyonel)', layers: 'Katmanlar', from_source: '+ Kaynaktan ekle', from_file: 'Dosya yükle', demo: 'Demo',
    convert: 'Dönüştür ve önizle', result: 'Sonuç', pay: 'Öde ve dosyaları indir', download: 'İndir (USD + GLB)',
    hint: 'Katman ekleyip "Dönüştür"e basın; önizleme burada görünecek', add_service: '+ Servis ekle', svc_name: 'Servis adı',
    sources_help: 'ArcGIS Server, GeoServer/WFS veya GeoJSON adreslerinizi kaydedin; katalogdan katman seçip dönüşüme ekleyin.',
    t_geojson: 'Tek dosya adresi', no_store: 'Yalnızca adres kaydedilir. Kullanıcı adı / parola / token hiçbir zaman saklanmaz; bağlanırken sorulur.',
    no_store_session: 'Bu bilgiler saklanmaz; yalnızca bu sekme açıkken bellekte tutulur.', cancel: 'Vazgeç', save: 'Kaydet',
    login_needed: 'Giriş gerekiyor mu? (kullanıcı adı / parola / token)', user: 'Kullanıcı adı', pass: 'Parola', tokenl: 'Token', connect: 'Bağlan',
    search: 'Katmanlarda ara…', catalog: 'Katalog', delete: 'Sil', info: 'Bilgi', add: '+ Ekle', added: 'Eklendi', loading: 'Yükleniyor…',
    found: 'katman', none_layers: 'Henüz katman yok. Kaynaktan ekleyin, dosya yükleyin ya da demo\'yu deneyin.', no_conns: 'Henüz servis eklenmemiş.',
    width: 'Çizgi genişliği (m)', height: 'Yükseklik (m)', hfield: 'Yükseklik alanı', zoff: 'Z ofseti (m)', color: 'Renk', srccrs: 'Kaynak CRS (opsiyonel)',
    where: 'Filtre (where)', psize: 'Nokta boyutu (m)', params: 'Parametreler', working: 'İşleniyor…', failed: 'Hata: ',
    features: 'nesne', tris: 'üçgen', truncated: 'Önizleme örneklenmiştir; teslimat tüm veriyi içerir.', paidnote: 'Ödeme alındı.',
    mock: 'Geliştirme modu: gerçek ödeme alınmaz.', login_req: 'Bu servis giriş istiyor; yukarıdan bilgileri girip "Bağlan"a basın.',
    j_name: 'Ad', j_status: 'Durum', j_price: 'Tutar', j_date: 'Tarih', j_paid: 'Ödendi', open: 'Aç', no_jobs: 'Henüz iş yok.', confirm_del: 'Servis silinsin mi?',
    need_layer: 'En az bir katman ekleyin.', geom: 'geometri', count: 'kayıt', fields: 'alan', line: 'çizgi', polygon: 'alan', point: 'nokta' },
  en: { tagline: 'Turn GIS data into 3D OpenUSD', nav_new: 'Convert', nav_sources: 'Sources', nav_jobs: 'My jobs',
    email: 'E-mail', password: 'Password (min. 10 characters)', login: 'Sign in', signup: 'Create account', logout: 'Sign out',
    project: 'Project', name: 'Name', crs: 'Target CRS', autoutm: 'Auto UTM', tile: 'Tile (m)', base: 'Base elevation (m)',
    anchor: 'Reference point X / Y (optional)', layers: 'Layers', from_source: '+ From source', from_file: 'Upload file', demo: 'Demo',
    convert: 'Convert & preview', result: 'Result', pay: 'Pay & download files', download: 'Download (USD + GLB)',
    hint: 'Add layers and press "Convert"; the preview appears here', add_service: '+ Add service', svc_name: 'Service name',
    sources_help: 'Save your ArcGIS Server, GeoServer/WFS or GeoJSON endpoints, then pick layers from the catalog.',
    t_geojson: 'Single file URL', no_store: 'Only the URL is saved. Username / password / token are never stored; you are asked when connecting.',
    no_store_session: 'Not stored; kept in memory only while this tab is open.', cancel: 'Cancel', save: 'Save',
    login_needed: 'Login required? (username / password / token)', user: 'Username', pass: 'Password', tokenl: 'Token', connect: 'Connect',
    search: 'Search layers…', catalog: 'Catalog', delete: 'Delete', info: 'Info', add: '+ Add', added: 'Added', loading: 'Loading…',
    found: 'layers', none_layers: 'No layers yet. Add from a source, upload a file or try the demo.', no_conns: 'No services yet.',
    width: 'Line width (m)', height: 'Height (m)', hfield: 'Height field', zoff: 'Z offset (m)', color: 'Color', srccrs: 'Source CRS (optional)',
    where: 'Filter (where)', psize: 'Point size (m)', params: 'Parameters', working: 'Processing…', failed: 'Error: ',
    features: 'features', tris: 'triangles', truncated: 'Preview is sampled; the delivery contains all data.', paidnote: 'Payment received.',
    mock: 'Dev mode: no real payment is taken.', login_req: 'This service needs a login; enter it above and press "Connect".',
    j_name: 'Name', j_status: 'Status', j_price: 'Price', j_date: 'Date', j_paid: 'Paid', open: 'Open', no_jobs: 'No jobs yet.', confirm_del: 'Delete this service?',
    need_layer: 'Add at least one layer.', geom: 'geometry', count: 'records', fields: 'fields', line: 'line', polygon: 'polygon', point: 'point' },
};
let lang = localStorage.lang || (navigator.language.startsWith('tr') ? 'tr' : 'en');
const $ = (s) => document.querySelector(s);
const t = (k) => T[lang][k] ?? k;
function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => (k === 'on' ? Object.entries(v).forEach(([a, f]) => e.addEventListener(a, f)) : k in e && k !== 'style' ? (e[k] = v) : e.setAttribute(k, v)));
  kids.flat().forEach((c) => c != null && e.append(c.nodeType ? c : document.createTextNode(c)));
  return e;
}
function i18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((e) => (e.textContent = t(e.dataset.i18n)));
  document.querySelectorAll('[data-i18n-ph]').forEach((e) => (e.placeholder = '🔍 ' + t(e.dataset.i18nPh)));
  $('#lang').textContent = lang === 'tr' ? 'EN' : 'TR';
  renderLayers(); renderConns(); if (view === 'jobs') loadJobs();
}
$('#lang').onclick = () => { lang = lang === 'tr' ? 'en' : 'tr'; localStorage.lang = lang; i18n(); };

/* ---------- api ---------- */
const api = (u, o = {}) => fetch(u, { credentials: 'same-origin', ...o, headers: { 'X-CSRF': '1', ...(o.headers || {}) } })
  .then((r) => { if (r.status === 401 && !u.startsWith('/api/auth/')) showAuth(); return r; });
const jpost = (u, body, method = 'POST') => api(u, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const errText = (b) => (typeof b.error === 'string' ? b.error : JSON.stringify(b.error));

/* ---------- routing ---------- */
let view = 'new';
function route() {
  view = (location.hash.match(/#\/(\w+)/) || [, 'new'])[1];
  if (!['new', 'sources', 'jobs'].includes(view)) view = 'new';
  ['new', 'sources', 'jobs'].forEach((v) => ($('#v-' + v).hidden = v !== view));
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.v === view));
  if (view === 'new') resize();
  if (view === 'sources') loadConns();
  if (view === 'jobs') loadJobs();
}
addEventListener('hashchange', route);

/* ---------- accounts ---------- */
function showAuth() { $('#auth').hidden = false; $('#who').hidden = true; }
async function authCall(kind) {
  const r = await fetch(`/api/auth/${kind}`, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF': '1', 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: $('#aemail').value, password: $('#apass').value }) });
  const b = await r.json();
  if (!r.ok) { $('#amsg').textContent = errText(b); return; }
  $('#apass').value = ''; $('#amsg').textContent = ''; onUser(b);
}
$('#authform').onsubmit = (e) => { e.preventDefault(); authCall('login'); };
$('#signup').onclick = () => authCall('signup');
$('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); location.href = '/'; };
function onUser(u) {
  $('#auth').hidden = true; $('#who').hidden = false; $('#email').textContent = u.email; $('#adminlink').hidden = !u.is_admin;
  route(); resumeJob();
}

/* ---------- layers state ---------- */
const layers = []; // {name, source, file?, fileObj?, url?, type_name?, connId?, geometry?, w,h,hf,zo,col,sc,where,ps}
const defaults = { w: 6, h: 0, hf: '', zo: 0.1, col: '#9aa5b1', sc: '', where: '1=1', ps: 1.5 };
const palette = ['#7b8794', '#d4c4a8', '#3fa34d', '#c98a5b', '#5b9bd5', '#b784d6', '#e0b84c'];
function addLayer(l) {
  let n = l.name, i = 2;
  while (layers.some((x) => x.name === n)) n = `${l.name}_${i++}`;
  layers.push({ ...defaults, col: palette[layers.length % palette.length], ...l, name: n });
  renderLayers();
}
function numField(l, key, label, step = 'any') {
  return el('label', {}, t(label), el('input', { type: 'number', step, value: l[key], on: { input: (e) => (l[key] = +e.target.value) } }));
}
function txtField(l, key, label, ph = '') {
  return el('label', {}, t(label), el('input', { value: l[key], placeholder: ph, on: { input: (e) => (l[key] = e.target.value) } }));
}
function renderLayers() {
  const box = $('#layers'); box.innerHTML = '';
  $('#lcount').textContent = layers.length || '';
  if (!layers.length) { box.append(el('div', { className: 'empty' }, t('none_layers'))); return; }
  layers.forEach((l, idx) => {
    const geom = l.geometry;
    const fields = [];
    if (!geom || geom === 'line') fields.push(numField(l, 'w', 'width', '0.5'));
    if (!geom || geom !== 'line') fields.push(numField(l, 'h', 'height'), txtField(l, 'hf', 'hfield'));
    if (geom === 'point') fields.push(numField(l, 'ps', 'psize', '0.5'));
    fields.push(numField(l, 'zo', 'zoff', '0.05'));
    if (l.source === 'arcgis') fields.push(txtField(l, 'where', 'where'));
    fields.push(txtField(l, 'sc', 'srccrs', 'EPSG:3857'));
    fields.push(el('label', {}, t('color'), el('input', { type: 'color', value: l.col, on: { input: (e) => { l.col = e.target.value; sw.style.background = l.col; } } })));
    const sw = el('span', { className: 'sw' }); sw.style.background = l.col;
    const sub = { upload: l.file || 'file', demo: 'demo', arcgis: 'ArcGIS', wfs: 'WFS', geojson_url: 'GeoJSON' }[l.source];
    box.append(el('div', { className: 'lyr' },
      el('div', { className: 'top' }, sw,
        el('div', { className: 'nm' }, el('b', {}, l.name), el('small', {}, sub, geom ? ` · ${t(geom)}` : '', l.count != null ? ` · ${Number(l.count).toLocaleString()}` : '')),
        el('span', { className: 'x', title: t('delete'), on: { click: () => { layers.splice(idx, 1); renderLayers(); } } }, '✕')),
      el('details', {}, el('summary', {}, t('params')), el('div', { className: 'g2' }, fields))));
  });
}
$('#demo').onclick = () => {
  layers.length = 0;
  addLayer({ name: 'roads', source: 'demo', url: 'roads', geometry: 'line', w: 8, col: '#7b8794' });
  addLayer({ name: 'buildings', source: 'demo', url: 'buildings', geometry: 'polygon', hf: 'height', zo: 0, col: '#d4c4a8' });
  addLayer({ name: 'trees', source: 'demo', url: 'trees', geometry: 'point', ps: 6, zo: 0, col: '#3fa34d' });
};
$('#addfile').onclick = () => $('#fileinput').click();
$('#fileinput').onchange = (e) => {
  [...e.target.files].forEach((f) => addLayer({ name: f.name.replace(/\.[^.]+$/, '').slice(0, 40) || 'layer', source: 'upload', file: f.name, fileObj: f }));
  e.target.value = '';
};

/* ---------- collect + job flow ---------- */
const creds = {}; // connId -> {username,password,token}; memory only, never persisted
function collect() {
  const up = new FormData();
  const spec = { name: $('#pname').value, crs_target: $('#crs').value, tile_size_m: +$('#tile').value || 1000, base_elevation_m: +$('#base').value || 0,
    layers: layers.map((l, i) => {
      const L = { name: l.name, source: l.source, line_width_m: l.w || 6, height_m: l.h || 0, z_offset_m: l.zo ?? 0, color: l.col, point_size_m: l.ps || 1.5 };
      if (l.hf?.trim()) L.height_field = l.hf.trim();
      if (l.sc?.trim()) L.source_crs = l.sc.trim().toUpperCase();
      if (l.source === 'upload') { const fn = `${i}_${l.file}`; L.file = fn; up.append('files', l.fileObj, fn); }
      else if (l.source === 'demo') { L.url = l.url; if (l.url === 'trees') L.point_height_m = 9; }
      else {
        L.url = l.url; if (l.type_name) L.type_name = l.type_name; if (l.source === 'arcgis') L.where = l.where || '1=1';
        const c = creds[l.connId] || {};
        if (c.username && c.password) { L.username = c.username; L.password = c.password; } else if (c.token) L.token = c.token;
      }
      return L;
    }) };
  if ($('#ax').value !== '' && $('#ay').value !== '') { spec.anchor_x = +$('#ax').value; spec.anchor_y = +$('#ay').value; }
  up.append('spec', JSON.stringify(spec));
  return up;
}
const msg = (s) => ($('#msg').textContent = s);
let job = null;
async function poll(id) {
  for (;;) {
    const j = await (await api(`/api/jobs/${id}`)).json();
    if (j.status === 'ready') return j;
    if (j.status === 'failed') throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 800));
  }
}
function renderResult(j) {
  job = j; $('#result').hidden = false; resize();
  const tot = j.report.totals;
  $('#stats').textContent = `${tot.features.toLocaleString()} ${t('features')} · ${tot.triangles.toLocaleString()} ${t('tris')}\n${j.report.target_crs}` + (j.report.preview_truncated ? '\n\n' + t('truncated') : '');
  $('#price').textContent = `$${(j.price_cents / 100).toFixed(2)}`;
  $('#pay').hidden = j.paid; $('#dl').hidden = !j.paid;
  $('#paynote').textContent = j.payment_mode === 'mock' && !j.paid ? t('mock') : '';
  if (j.paid) { $('#dl').href = `/api/jobs/${j.id}/download`; $('#wm').hidden = true; }
}
async function start() {
  if (!layers.length) { msg(t('need_layer')); return; }
  $('#go').disabled = true; $('#result').hidden = true;
  try {
    msg(t('working'));
    const r = await api('/api/jobs', { method: 'POST', body: collect() });
    const body = await r.json();
    if (!r.ok) throw new Error(errText(body));
    history.replaceState(null, '', `?job=${body.id}#/new`);
    const j = await poll(body.id);
    msg(''); showGLB(`/api/jobs/${j.id}/preview.glb`); renderResult(j);
  } catch (e) { msg(t('failed') + e.message); }
  $('#go').disabled = false;
}
$('#go').onclick = start;
$('#pay').onclick = async () => {
  const r = await (await api(`/api/jobs/${job.id}/checkout`, { method: 'POST' })).json();
  if (r.url) { location.href = r.url; return; }
  if (r.mock) await api(`/api/jobs/${job.id}/mock-pay`, { method: 'POST' });
  renderResult(await (await api(`/api/jobs/${job.id}`)).json()); msg(t('paidnote'));
};
async function resumeJob() {
  const qid = new URLSearchParams(location.search).get('job');
  if (!qid) return;
  const r = await api(`/api/jobs/${qid}/verify-payment`, { method: 'POST' });
  if (!r.ok) return; const j = await r.json();
  if (j.status === 'ready') { showGLB(`/api/jobs/${qid}/preview.glb`); renderResult(j); }
}

/* ---------- viewer ---------- */
const vw = $('#view');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio); vw.append(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0d1117);
const cam = new THREE.PerspectiveCamera(50, 1, 1, 100000);
const controls = new OrbitControls(cam, renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.8); sun.position.set(300, 600, 200); scene.add(sun);
const grid = new THREE.GridHelper(2000, 40, 0x334455, 0x1d2733); scene.add(grid);
let model;
function resize() { const w = vw.clientWidth, h = vw.clientHeight; if (!w || !h) return; renderer.setSize(w, h); cam.aspect = w / h; cam.updateProjectionMatrix(); }
addEventListener('resize', resize); new ResizeObserver(resize).observe(vw);
(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, cam); })();
function showGLB(url) {
  new GLTFLoader().load(url, (g) => {
    if (model) scene.remove(model);
    model = g.scene; scene.add(model);
    const box = new THREE.Box3().setFromObject(model), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const r = Math.max(s.x, s.z, 50);
    cam.position.set(c.x + r * 0.8, c.y + r * 0.8, c.z + r * 0.8); controls.target.copy(c); controls.update();
    grid.position.set(c.x, box.min.y - 0.2, c.z); $('#hint').hidden = true; $('#wm').hidden = false;
  });
}

/* ---------- sources ---------- */
let conns = [];
async function loadConns() { const r = await api('/api/connections'); if (r.ok) { conns = await r.json(); renderConns(); } }
const kindName = { arcgis: 'ArcGIS Server', wfs: 'GeoServer / WFS', geojson_url: 'GeoJSON URL' };
function renderConns() {
  const box = $('#conns'); box.innerHTML = '';
  if (!conns.length) { box.append(el('div', { className: 'empty' }, t('no_conns'))); return; }
  conns.forEach((c) => box.append(el('div', { className: 'card conn' },
    el('div', { className: 'rowh' }, el('b', {}, c.name), el('span', { className: 'badge' }, kindName[c.kind])),
    el('div', { className: 'u' }, c.url),
    el('div', { className: 'btns' },
      el('button', { className: 'primary sm', on: { click: () => openCatalog(c) } }, t('catalog')),
      el('button', { className: 'ghost sm danger', on: { click: async () => { if (confirm(t('confirm_del'))) { await api(`/api/connections/${c.id}`, { method: 'DELETE' }); loadConns(); } } } }, t('delete'))))));
}
const hints = { arcgis: 'https://sunucu/arcgis/rest/services  (veya …/FeatureServer, …/FeatureServer/0)', wfs: 'https://sunucu/geoserver/ows  (veya …/wfs)', geojson_url: 'https://…/veri.geojson' };
const showSvc = () => { const k = document.querySelector('input[name=kind]:checked').value; $('#svchint').textContent = hints[k]; };
document.querySelectorAll('input[name=kind]').forEach((r) => (r.onchange = showSvc));
$('#newsvc').onclick = () => { $('#svcform').reset(); $('#svcmsg').textContent = ''; showSvc(); $('#m-svc').hidden = false; };
$('#svcform').onsubmit = async (e) => {
  e.preventDefault();
  const r = await jpost('/api/connections', { kind: document.querySelector('input[name=kind]:checked').value, name: $('#svcname').value, url: $('#svcurl').value });
  const b = await r.json();
  if (!r.ok) { $('#svcmsg').textContent = errText(b); return; }
  $('#m-svc').hidden = true; await loadConns();
  if (view === 'sources') openCatalog(conns.find((c) => c.id === b.id));
};
document.querySelectorAll('[data-close]').forEach((b) => (b.onclick = () => b.closest('.overlay').hidden = true));
document.querySelectorAll('.overlay').forEach((o) => o.addEventListener('mousedown', (e) => { if (e.target === o && o.id !== 'auth') o.hidden = true; }));

/* ---------- catalog browser ---------- */
let cur = null, catLayers = [];
function credsBody(id) { return { ...(creds[id] || {}) }; }
async function openCatalog(c) {
  cur = c; $('#cattitle').textContent = c.name; $('#catq').value = ''; $('#catlist').innerHTML = '';
  const cr = creds[c.id] || {}; $('#cuser').value = cr.username || ''; $('#cpass').value = cr.password || ''; $('#ctoken').value = cr.token || '';
  $('#credbox').open = false; $('#m-cat').hidden = false; await loadCatalog();
}
async function loadCatalog() {
  $('#catstatus').textContent = t('loading'); $('#catlist').innerHTML = '';
  const r = await jpost(`/api/connections/${cur.id}/catalog`, credsBody(cur.id)); const b = await r.json();
  if (!r.ok) {
    $('#catstatus').textContent = errText(b); $('#catstatus').className = 'warn';
    if (/login|token|401|403/i.test(errText(b))) { $('#credbox').open = true; $('#catstatus').textContent += '\n' + t('login_req'); }
    return;
  }
  $('#catstatus').className = 'muted'; catLayers = b.layers; renderCatalog();
}
$('#cconnect').onclick = () => {
  creds[cur.id] = { username: $('#cuser').value, password: $('#cpass').value, token: $('#ctoken').value.trim() };
  loadCatalog();
};
$('#catq').oninput = renderCatalog;
function renderCatalog() {
  const q = $('#catq').value.toLowerCase(), box = $('#catlist'); box.innerHTML = '';
  const list = catLayers.filter((l) => !q || `${l.name} ${l.group}`.toLowerCase().includes(q));
  $('#catstatus').textContent = `${list.length} ${t('found')}`;
  let grp = null;
  list.slice(0, 400).forEach((l) => {
    if (l.group !== grp) { grp = l.group; if (grp) box.append(el('div', { className: 'grp' }, grp)); }
    const meta = el('div', { className: 'meta' });
    const row = el('div', { className: 'crow' }, el('div', { className: 'nm' }, el('b', {}, l.name), meta),
      el('button', { className: 'ghost sm', on: { click: async (e) => {
        e.target.disabled = true; meta.textContent = t('loading');
        const r = await jpost(`/api/connections/${cur.id}/info`, { ref: l.ref, ...credsBody(cur.id) }); const b = await r.json();
        meta.textContent = r.ok ? `${t(b.geometry) || '?'} · ${b.count != null ? Number(b.count).toLocaleString() : '?'} ${t('count')} · ${b.fields.length} ${t('fields')}${b.fields.length ? ': ' + b.fields.slice(0, 6).map((f) => f.name).join(', ') : ''}` : errText(b);
        l.info = r.ok ? b : null; e.target.disabled = false;
      } } }, t('info')),
      el('button', { className: 'primary sm', on: { click: (e) => {
        const base = { name: l.name.replace(/[^\w\-]+/g, '_').slice(0, 40) || 'layer', connId: cur.id, geometry: l.info?.geometry, count: l.info?.count };
        if (cur.kind === 'wfs') addLayer({ ...base, source: 'wfs', url: cur.url, type_name: l.ref });
        else if (cur.kind === 'arcgis') addLayer({ ...base, source: 'arcgis', url: l.ref });
        else addLayer({ ...base, source: 'geojson_url', url: l.ref });
        e.target.textContent = '✓ ' + t('added');
      } } }, t('add')));
    box.append(row);
  });
}
$('#addsrc').onclick = async () => {
  await loadConns();
  if (!conns.length) { location.hash = '#/sources'; return; }
  if (conns.length === 1) { openCatalog(conns[0]); return; }
  const pick = el('div', { className: 'overlay' }, el('div', { className: 'card pad wide' }, el('h2', {}, t('nav_sources')),
    conns.map((c) => el('div', { className: 'crow' }, el('div', { className: 'nm' }, el('b', {}, c.name), el('div', { className: 'meta' }, kindName[c.kind])),
      el('button', { className: 'primary sm', on: { click: () => { pick.remove(); openCatalog(c); } } }, t('catalog')))),
    el('button', { className: 'ghost', on: { click: () => pick.remove() } }, t('cancel'))));
  document.body.append(pick);
};

/* ---------- jobs ---------- */
async function loadJobs() {
  const r = await api('/api/my/jobs'); if (!r.ok) return; const list = await r.json();
  const tb = $('#jobtable'); tb.innerHTML = '';
  if (!list.length) { tb.append(el('tr', {}, el('td', {}, t('no_jobs')))); return; }
  tb.append(el('tr', {}, ['j_name', 'j_status', 'j_price', 'j_paid', 'j_date', ''].map((h) => el('th', {}, h ? t(h) : ''))));
  list.forEach((j) => tb.append(el('tr', {}, el('td', {}, j.name), el('td', {}, j.status), el('td', {}, '$' + (j.price_cents / 100).toFixed(2)),
    el('td', {}, j.paid ? '✓' : ''), el('td', {}, new Date(j.created * 1000).toLocaleString()),
    el('td', {}, j.status === 'ready' ? el('a', { on: { click: () => { location.href = `/?job=${j.id}#/new`; } } }, t('open')) : ''))));
}

/* ---------- boot ---------- */
(async () => {
  i18n();
  const r = await fetch('/api/auth/me', { credentials: 'same-origin' });
  if (r.ok) onUser(await r.json()); else showAuth();
})();
