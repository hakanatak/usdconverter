import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/* ---------- i18n ---------- */
const T = {
  tr: { st1: 'Veri', st2: 'Ayarlar', st3: 'Önizleme', s1_title: 'Verinizi ekleyin', s2_title: 'Neredeyse hazır', s2_sub: 'Ayarları veriden otomatik doldurduk. İsterseniz değiştirin, değilse doğrudan önizleyin.',
    or: 'ya da', alt_service: 'Servisten ekle', alt_service_sub: 'ArcGIS Server · GeoServer/WFS · GeoJSON URL', alt_demo: 'Demo veriyle dene', alt_demo_sub: 'Yol, bina ve ağaç içeren örnek bölge',
    next: 'Devam →', back: '← Geri', advanced: 'Gelişmiş ayarlar', tweak: '← Ayarları değiştir', again: 'Yeni dönüşüm', reading: 'Okunuyor…',
    needs_crs: 'Koordinat sistemi dosyada yok. Hangisi?', apply: 'Uygula', other: 'Diğer…', n_feat: 'nesne',
    road_w: 'Yol genişliği', bld_h: 'Bina yüksekliği', from_data: 'veriden', h_field: 'Veriden', h_fixed: 'Sabit', h_flat: 'Düz', hf_field: 'Alan', pt_size: 'Nesne boyutu', pt_h: 'Nesne yüksekliği',
    w_data: 'Veriden', w_fixed: 'Sabit', floors_note: 'kat sayısı × 3 m', dflt_conn: 'Servisten', zf: 'Kot alanı (Z)', none: '— yok —', mixed: 'Karışık geometri: yalnızca baskın tür kullanılır.',
    unit_m: 'm', layer_name: 'Katman adı', tagline: 'CBS verisini 3B OpenUSD\'ye dönüştür', nav_new: 'Dönüşüm', nav_sources: 'Kaynaklar', nav_jobs: 'İşlerim',
    email: 'E-posta', password: 'Parola (en az 10 karakter)', login: 'Giriş yap', signup: 'Hesap oluştur', logout: 'Çıkış',
    project: 'Proje', name: 'Ad', crs: 'Hedef CRS', autoutm: 'Otomatik UTM', tile: 'Karo (m)', base: 'Taban kotu (m)',
    anchor: 'Referans noktası X / Y (opsiyonel)', layers: 'Katmanlar', from_source: '+ Kaynaktan ekle', from_file: 'Dosya yükle', drop_title: 'Dosyalarınızı buraya sürükleyip bırakın', drop_sub: 'ya da tıklayıp seçin · GeoJSON (.geojson / .json) · en fazla 50 MB', drop_release: 'Bırakın: katman olarak eklensin', bad_file: 'Desteklenmeyen dosya (şimdilik yalnızca GeoJSON): ', too_big: 'Dosya çok büyük: ', demo: 'Demo',
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
  en: { st1: 'Data', st2: 'Settings', st3: 'Preview', s1_title: 'Add your data', s2_title: 'Almost ready', s2_sub: 'We filled in the settings from your data. Change them if you like, or go straight to the preview.',
    or: 'or', alt_service: 'Add from a service', alt_service_sub: 'ArcGIS Server · GeoServer/WFS · GeoJSON URL', alt_demo: 'Try with demo data', alt_demo_sub: 'Sample area with roads, buildings and trees',
    next: 'Continue →', back: '← Back', advanced: 'Advanced settings', tweak: '← Change settings', again: 'New conversion', reading: 'Reading…',
    needs_crs: 'The file has no coordinate system. Which one?', apply: 'Apply', other: 'Other…', n_feat: 'features',
    road_w: 'Road width', bld_h: 'Building height', from_data: 'from data', h_field: 'From data', h_fixed: 'Fixed', h_flat: 'Flat', hf_field: 'Field', pt_size: 'Object size', pt_h: 'Object height',
    w_data: 'From data', w_fixed: 'Fixed', floors_note: 'storeys × 3 m', dflt_conn: 'From service', zf: 'Elevation field (Z)', none: '— none —', mixed: 'Mixed geometry: only the dominant type is used.',
    unit_m: 'm', layer_name: 'Layer name', tagline: 'Turn GIS data into 3D OpenUSD', nav_new: 'Convert', nav_sources: 'Sources', nav_jobs: 'My jobs',
    email: 'E-mail', password: 'Password (min. 10 characters)', login: 'Sign in', signup: 'Create account', logout: 'Sign out',
    project: 'Project', name: 'Name', crs: 'Target CRS', autoutm: 'Auto UTM', tile: 'Tile (m)', base: 'Base elevation (m)',
    anchor: 'Reference point X / Y (optional)', layers: 'Layers', from_source: '+ From source', from_file: 'Upload file', drop_title: 'Drag & drop your files here', drop_sub: 'or click to choose · GeoJSON (.geojson / .json) · max 50 MB', drop_release: 'Release to add as layers', bad_file: 'Unsupported file (GeoJSON only for now): ', too_big: 'File too large: ', demo: 'Demo',
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
  renderAdded(); renderLayers(); renderConns(); if (view === 'jobs') loadJobs();
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
  if (view === 'new') { resize(); renderAdded(); }
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

/* ---------- wizard ---------- */
let step = 1;
function goStep(n) {
  step = n;
  [1, 2, 3].forEach((i) => ($('#s' + i).hidden = i !== n));
  document.querySelectorAll('#stepper li').forEach((li) => { const i = +li.dataset.s; li.classList.toggle('on', i === n); li.classList.toggle('done', i < n); });
  if (n === 2) prepareStep2();
  if (n === 3) resize();
}
document.querySelectorAll('#stepper li').forEach((li) => (li.onclick = () => { const i = +li.dataset.s; if (i < step && !(i === 3)) goStep(i); }));
$('#next1').onclick = () => goStep(2);
$('#back2').onclick = () => goStep(1);
$('#tweak').onclick = () => goStep(2);
$('#again').onclick = () => { layers.length = 0; renderAdded(); renderLayers(); $('#result').hidden = true; history.replaceState(null, '', '/#/new'); goStep(1); };

/* ---------- layers state ---------- */
// layer: {id,name,source,file?,fileObj?,url?,type_name?,connId?, state:'reading'|'ok'|'needs_crs'|'error', info?, msg?, sc?, ...settings}
let lid = 0;
const layers = [];
const unique = (base) => { let n = base, i = 2; while (layers.some((x) => x.name === n)) n = `${base}_${i++}`; return n; };
function applyInfo(l, info) {
  const sg = info.suggest || {};
  l.info = info; l.geometry = info.geometry; l.count = info.count; l.state = 'ok';
  l.col = sg.color || '#9aa5b1'; l.w = sg.width_m ?? 6; l.zo = l.geometry === 'line' ? 0.15 : 0.05; l.zf = sg.z_field || '';
  l.wf = sg.width_field || ''; l.wmode = l.wf ? 'field' : 'fixed';
  l.hf = sg.height_field || ''; l.hscale = sg.height_scale || 1; l.h = sg.height_m || 0;
  l.hmode = l.hf ? 'field' : (l.h > 0 ? 'fixed' : 'flat'); if (l.h === 0) l.h = 10;
  l.ps = sg.point_size_m ?? 2; l.ph = sg.point_height_m ?? 6;
  l.where = '1=1';
}
function newLayer(o) { const l = { id: ++lid, state: 'reading', ...o, name: unique(o.name) }; layers.push(l); renderAdded(); return l; }
const geomLabel = (g) => (g ? t(g) : '?');
function layerSummary(l) {
  if (l.state === 'reading') return t('reading');
  if (l.state === 'error') return l.msg;
  const bits = [geomLabel(l.geometry), l.count != null ? `${Number(l.count).toLocaleString()} ${t('n_feat')}` : null, l.info?.crs, l.source === 'demo' ? 'demo' : null].filter(Boolean);
  return bits.join(' · ');
}
function renderAdded() {
  const box = $('#added'); box.innerHTML = '';
  layers.forEach((l, idx) => {
    const item = el('div', { className: 'item' + (l.state === 'error' || l.state === 'needs_crs' ? ' err' : '') },
      el('div', { className: 'st' }, l.state === 'reading' ? el('div', { className: 'spin', style: 'margin:0;width:20px;height:20px' }) : l.state === 'ok' ? el('span', { className: 'ok' }, '✓') : '⚠'),
      el('div', { className: 'nm' }, el('b', {}, l.name), el('small', {}, l.state === 'needs_crs' ? l.msg : layerSummary(l)),
        l.state === 'needs_crs' ? crsAsk(l) : null),
      el('span', { className: 'x', title: t('delete'), on: { click: () => { layers.splice(idx, 1); renderAdded(); } } }, '✕'));
    box.append(item);
  });
  $('#next1').disabled = !layers.length || layers.some((l) => l.state !== 'ok');
}
function crsAsk(l) {
  const sel = el('select', {}, ['EPSG:3857', 'EPSG:32635', 'EPSG:32636', 'EPSG:5254', 'EPSG:2154', 'EPSG:27700'].map((c) => el('option', { value: c }, c)), el('option', { value: '' }, t('other')));
  const own = el('input', { placeholder: 'EPSG:xxxx', hidden: true, size: 12 });
  sel.onchange = () => (own.hidden = sel.value !== '');
  return el('div', { className: 'crsask' }, sel, own, el('button', { className: 'primary sm', on: { click: () => inspectFile(l, (sel.value || own.value).trim().toUpperCase()) } }, t('apply')));
}
async function inspectFile(l, crs = '') {
  l.state = 'reading'; renderAdded();
  const fd = new FormData(); fd.append('file', l.fileObj, l.file); fd.append('source_crs', crs);
  try {
    const r = await api('/api/inspect', { method: 'POST', body: fd }); const b = await r.json();
    if (!r.ok) { l.state = 'error'; l.msg = errText(b); }
    else if (b.needs_crs) { l.state = 'needs_crs'; l.msg = t('needs_crs'); }
    else { applyInfo(l, b); l.sc = crs; l.mixed = b.mixed; l.tile = b.suggested_tile_m; }
  } catch (e) { l.state = 'error'; l.msg = e.message; }
  renderAdded();
}
function addFiles(files) {
  const bad = [];
  [...files].forEach((f) => {
    if (!/\.(geojson|json)$/i.test(f.name)) { bad.push(t('bad_file') + f.name); return; }
    if (f.size > 50 * 1024 * 1024) { bad.push(t('too_big') + f.name); return; }
    const l = newLayer({ name: f.name.replace(/\.[^.]+$/, '').replace(/[^\w\-]+/g, '_').slice(0, 40) || 'layer', source: 'upload', file: f.name, fileObj: f });
    if (layers.length === 1 && $('#pname').value === 'My project') $('#pname').value = l.name;
    inspectFile(l);
  });
  $('#msg1').textContent = bad.join('\n');
}
function addServiceLayer(base, info) { const l = newLayer(base); applyInfo(l, info); renderAdded(); }
$('#demo').onclick = () => {
  layers.length = 0;
  const mk = (name, geometry, count, sg) => { const l = newLayer({ name, source: 'demo', url: name }); applyInfo(l, { geometry, count, suggest: sg, crs: 'EPSG:4326' }); l.tile = 250; return l; };
  mk('roads', 'line', 19, { color: '#7b8794', width_m: 8 });
  mk('buildings', 'polygon', 64, { color: '#d4c4a8', height_field: 'height' });
  mk('trees', 'point', 64, { color: '#3fa34d', point_size_m: 6, point_height_m: 9 });
  $('#pname').value = 'Demo'; renderAdded();
};
$('#drop').onclick = () => $('#fileinput').click();
$('#drop').onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') $('#fileinput').click(); };
$('#fileinput').onchange = (e) => { addFiles(e.target.files); e.target.value = ''; };
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
const dropOK = () => view === 'new' && step <= 2;
addEventListener('dragenter', (e) => { if (hasFiles(e) && dropOK()) { dragDepth++; $('#dragveil').hidden = false; $('#drop').classList.add('over'); } });
addEventListener('dragleave', (e) => { if (hasFiles(e) && --dragDepth <= 0) { dragDepth = 0; $('#dragveil').hidden = true; $('#drop').classList.remove('over'); } });
addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
addEventListener('drop', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth = 0; $('#dragveil').hidden = true; $('#drop').classList.remove('over');
  if (dropOK()) { if (step === 2) goStep(1); addFiles(e.dataTransfer.files); }
});

/* ---------- step 2: per-layer cards (one or two smart controls each) ---------- */
function seg(options, value, onpick) {
  const box = el('div', { className: 'seg' });
  options.forEach(([v, label]) => box.append(el('button', { className: v === value ? 'on' : '', type: 'button', on: { click: () => { onpick(v); renderLayers(); } } }, label)));
  return box;
}
function range(l, key, min, max, step, unit = t('unit_m')) {
  const out = el('output', {}, `${l[key]} ${unit}`);
  const inp = el('input', { type: 'range', min, max, step, value: l[key], on: { input: (e) => { l[key] = +e.target.value; out.textContent = `${l[key]} ${unit}`; } } });
  return el('div', { className: 'rng' }, inp, out);
}
const ctl = (label, ...kids) => el('div', { className: 'ctl' }, el('span', { className: 'lab' }, label), ...kids);
const numFields = (l) => (l.info?.fields || []).filter((f) => f.numeric).map((f) => f.name);
function fieldSelect(l, key, names, withNone = false) {
  return el('select', { on: { change: (e) => { l[key] = e.target.value; } } },
    withNone ? el('option', { value: '' }, t('none')) : null,
    names.map((n) => el('option', { value: n, selected: n === l[key] }, n)));
}
function layerControls(l) {
  const nums = numFields(l);
  if (l.geometry === 'line') {
    const c = [];
    if (nums.length) c.push(seg([['fixed', t('w_fixed')], ['field', t('w_data')]], l.wmode, (v) => { l.wmode = v; if (v === 'field' && !l.wf) l.wf = nums[0]; }));
    c.push(l.wmode === 'field' ? fieldSelect(l, 'wf', nums) : range(l, 'w', 1, 30, 0.5));
    return ctl(t('road_w'), ...c);
  }
  if (l.geometry === 'polygon') {
    const opts = [['flat', t('h_flat')], ['fixed', t('h_fixed')]]; if (nums.length) opts.push(['field', t('h_field')]);
    const c = [seg(opts, l.hmode, (v) => { l.hmode = v; if (v === 'field' && !l.hf) l.hf = nums[0]; })];
    if (l.hmode === 'fixed') c.push(range(l, 'h', 1, 200, 1));
    if (l.hmode === 'field') { c.push(fieldSelect(l, 'hf', nums)); if (l.hscale !== 1) c.push(el('span', { className: 'auto' }, `${t('floors_note')}`)); }
    return ctl(t('bld_h'), ...c);
  }
  if (l.geometry === 'point') return el('div', {}, ctl(t('pt_size'), range(l, 'ps', 0.5, 30, 0.5)), ctl(t('pt_h'), range(l, 'ph', 0.5, 60, 0.5)));
  return null;
}
function renderLayers() {
  const box = $('#layers'); box.innerHTML = '';
  layers.filter((l) => l.state === 'ok').forEach((l) => {
    const adv = el('details', { className: 'adv' }, el('summary', {}, t('advanced')),
      el('div', { className: 'g2' },
        el('label', {}, t('zoff'), el('input', { type: 'number', step: '0.05', value: l.zo, on: { input: (e) => (l.zo = +e.target.value) } })),
        el('label', {}, t('zf'), fieldSelect(l, 'zf', numFields(l), true)),
        el('label', {}, t('srccrs'), el('input', { value: l.sc || '', placeholder: 'EPSG:3857', on: { input: (e) => (l.sc = e.target.value) } })),
        l.source === 'arcgis' ? el('label', {}, t('where'), el('input', { value: l.where, on: { input: (e) => (l.where = e.target.value) } })) : null));
    box.append(el('div', { className: 'lcard' },
      el('div', { className: 'head' },
        el('input', { type: 'color', value: l.col, on: { input: (e) => (l.col = e.target.value) } }),
        el('input', { type: 'text', className: 'ln', value: l.name, 'aria-label': t('layer_name'), on: { change: (e) => { l.name = e.target.value.replace(/[^\w\-]+/g, '_').slice(0, 40) || l.name; e.target.value = l.name; } } }),
        el('span', { className: 'detect' }, layerSummary(l))),
      l.mixed ? el('p', { className: 'muted small' }, t('mixed')) : null,
      layerControls(l), adv));
  });
}
let tileTouched = false;
$('#tile').addEventListener('input', () => (tileTouched = true));
function prepareStep2() {
  renderLayers();
  if (!tileTouched) { const ts = layers.map((l) => l.tile).filter(Boolean); if (ts.length) $('#tile').value = Math.max(...ts); }
  msg('');
}

/* ---------- collect + job flow ---------- */
const creds = {}; // connId -> {username,password,token}; memory only, never persisted
function collect() {
  const up = new FormData();
  const spec = { name: $('#pname').value || 'Project', crs_target: $('#crs').value, tile_size_m: +$('#tile').value || 1000, base_elevation_m: +$('#base').value || 0,
    layers: layers.map((l, i) => {
      const L = { name: l.name, source: l.source, color: l.col, z_offset_m: l.zo ?? 0 };
      if (l.geometry === 'line') { L.line_width_m = l.w || 6; if (l.wmode === 'field' && l.wf) L.width_field = l.wf; }
      if (l.geometry === 'polygon') {
        if (l.hmode === 'field' && l.hf) { L.height_field = l.hf; L.height_scale = l.hscale || 1; } else if (l.hmode === 'fixed') L.height_m = l.h;
      }
      if (l.geometry === 'point') { L.point_size_m = l.ps; L.point_height_m = l.ph; }
      if (l.zf) L.z_field = l.zf;
      if (l.sc?.trim()) L.source_crs = l.sc.trim().toUpperCase();
      if (l.source === 'upload') { const fn = `${i}_${l.file}`; L.file = fn; up.append('files', l.fileObj, fn); }
      else if (l.source === 'demo') { L.url = l.url; }
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
  $('#go').disabled = true; msg('');
  $('#result').hidden = true; if (model) { scene.remove(model); model = null; } $('#hint').hidden = false; $('#wm').hidden = true;
  goStep(3);
  try {
    const r = await api('/api/jobs', { method: 'POST', body: collect() });
    const body = await r.json();
    if (!r.ok) throw new Error(errText(body));
    history.replaceState(null, '', `?job=${body.id}#/new`);
    const j = await poll(body.id);
    showGLB(`/api/jobs/${j.id}/preview.glb`); renderResult(j);
  } catch (e) { goStep(2); msg(t('failed') + e.message); }
  $('#go').disabled = false;
}
$('#go').onclick = start;
$('#pay').onclick = async () => {
  const r = await (await api(`/api/jobs/${job.id}/checkout`, { method: 'POST' })).json();
  if (r.url) { location.href = r.url; return; }
  if (r.mock) await api(`/api/jobs/${job.id}/mock-pay`, { method: 'POST' });
  renderResult(await (await api(`/api/jobs/${job.id}`)).json());
};
async function resumeJob() {
  const qid = new URLSearchParams(location.search).get('job');
  if (!qid) return;
  const r = await api(`/api/jobs/${qid}/verify-payment`, { method: 'POST' });
  if (!r.ok) return; const j = await r.json();
  if (j.status === 'ready') { goStep(3); showGLB(`/api/jobs/${qid}/preview.glb`); renderResult(j); }
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
    grid.position.set(c.x, box.min.y - 0.2, c.z); $('#hint').hidden = true; $('#wm').hidden = !!(job && job.paid);
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
      el('button', { className: 'primary sm', on: { click: async (e) => {
        e.target.disabled = true;
        let info = l.info;
        if (!info) {
          const r = await jpost(`/api/connections/${cur.id}/info`, { ref: l.ref, ...credsBody(cur.id) }); const b = await r.json();
          if (!r.ok) { meta.textContent = errText(b); e.target.disabled = false; return; }
          info = l.info = b;
        }
        const base = { name: l.name.replace(/[^\w\-]+/g, '_').slice(0, 40) || 'layer', connId: cur.id };
        if (cur.kind === 'wfs') addServiceLayer({ ...base, source: 'wfs', url: cur.url, type_name: l.ref }, info);
        else if (cur.kind === 'arcgis') addServiceLayer({ ...base, source: 'arcgis', url: l.ref }, info);
        else addServiceLayer({ ...base, source: 'geojson_url', url: l.ref }, info);
        e.target.textContent = '✓ ' + t('added');
      } } }, t('add')));
    box.append(row);
  });
}
$('#addsrc').onclick = async () => {
  await loadConns();
  if (!conns.length) { location.hash = '#/sources'; $('#newsvc').click(); return; }
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
  i18n(); goStep(1);
  const r = await fetch('/api/auth/me', { credentials: 'same-origin' });
  if (r.ok) onUser(await r.json()); else showAuth();
})();
