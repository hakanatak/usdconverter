const d = (t) => (t ? new Date(t * 1000).toLocaleString() : '');
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function table(id, head, rows) {
  document.getElementById(id).innerHTML = '<tr>' + head.map((h) => `<th>${h}</th>`).join('') + '</tr>' +
    rows.map((r) => '<tr>' + r.map((c) => `<td>${esc(c)}</td>`).join('') + '</tr>').join('');
}
fetch('/api/admin/overview', { credentials: 'same-origin' }).then(async (r) => {
  if (!r.ok) { document.getElementById('err').textContent = r.status === 401 ? 'Please sign in first.' : 'Admins only.'; return; }
  const o = await r.json();
  table('sessions', ['User', 'IP', 'Browser', 'Signed in', 'Last seen'], o.sessions.map((s) => [s.email, s.ip, s.ua, d(s.created), d(s.last_seen)]));
  table('users', ['E-mail', 'Admin', 'Jobs', 'Registered', 'Last login'], o.users.map((u) => [u.email, u.is_admin ? 'yes' : '', u.jobs, d(u.created), d(u.last_login)]));
  table('jobs', ['User', 'Name', 'Status', 'Price', 'Paid', 'Created'], o.jobs.map((j) => [j.email, j.name, j.status, '$' + (j.price_cents / 100).toFixed(2), j.paid ? 'yes' : '', d(j.created)]));
});
