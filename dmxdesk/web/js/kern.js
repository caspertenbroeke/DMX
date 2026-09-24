// Kern: verbinding met DMXDesk, gedeelde toestand en kleine hulpjes voor alle tabbladen.

export const K = {
  S: null,               // volledige toestand (GET /api/state)
  L: { s: null, v: [] }, // live: status en voorbeeld per lamp (Server-Sent Events)
  wijziging: 0,
  bezig: false,          // gebruiker sleept aan een schuif: niet opnieuw tekenen
  monitor: 0,            // universe voor het DMX-monitor-tabblad (0 = geen frames meesturen)
};

// ------------------------------------------------------------------ gebeurtenissen
const luisteraars = {};
export function op(naam, fn) { (luisteraars[naam] ||= []).push(fn); return () => af(naam, fn); }
export function af(naam, fn) { luisteraars[naam] = (luisteraars[naam] || []).filter(f => f !== fn); }
export function meld(naam, data) { for (const fn of luisteraars[naam] || []) { try { fn(data); } catch (e) { console.error(e); } } }

// ------------------------------------------------------------------ API
export async function api(url, body) {
  const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const r = await fetch(url, opt);
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && j.pin) { toonPin(); throw new Error('Pincode nodig'); }
  if (!r.ok) throw new Error(j.fout || ('Fout ' + r.status));
  return j;
}

export async function doe(url, body, gelukt) {
  try { const j = await api(url, body); if (gelukt) toast(gelukt); return j; }
  catch (e) { toast(e.message, true); return null; }
}

let laadVol = false, bezigLaden = null, volgendeLaden = null;
async function echtLaden() {
  const volledig = laadVol || !K.S || (K.L.s && K.L.s.patch_versie !== K.S.status.patch_versie);
  laadVol = false;
  try {
    const nieuw = await api('/api/state' + (volledig ? '' : '?deel=licht'));
    if (!volledig) { nieuw.fixtures = K.S.fixtures; nieuw.profielen = K.S.profielen; nieuw.status.patch_versie = K.S.status.patch_versie; }
    K.S = nieuw;
    K.wijziging = K.S.status.wijziging;
    meld('state', K.S);
  } catch (e) { /* verbinding weg: de live-verbinding meldt dat al */ }
  return K.S;
}
export function laadState(vol = false) {
  // nooit twee tegelijk; wie tijdens het laden vraagt, wacht op de volgende (verse) laadronde
  if (vol) laadVol = true;
  if (!bezigLaden) { bezigLaden = echtLaden().finally(() => { bezigLaden = null; }); return bezigLaden; }
  if (!volgendeLaden) volgendeLaden = bezigLaden.then(() => { volgendeLaden = null; return laadState(); });
  return volgendeLaden;
}

export function pad(p, v) {
  const keys = p.split('.'), obj = {}; let o = obj;
  keys.slice(0, -1).forEach(k => o = o[k] = {});
  o[keys[keys.length - 1]] = v;
  return obj;
}
export async function zetShow(p, v, herladen = true) {
  // meteen lokaal bijwerken, zodat het scherm niet terugspringt
  const keys = p.split('.'); let o = K.S.show;
  keys.slice(0, -1).forEach(k => o = o[k] ||= {});
  o[keys[keys.length - 1]] = v;
  try { await api('/api/show', pad(p, v)); } catch (e) { toast(e.message, true); }
  if (herladen) await laadState();
}

// ------------------------------------------------------------------ live-verbinding
let bron = null, bronMonitor = null, geenVerbinding = null;
export function startLive() {
  if (bron && bronMonitor === K.monitor) return;
  if (bron) bron.close();
  bronMonitor = K.monitor;
  bron = new EventSource('/api/live' + (K.monitor ? '?monitor=' + K.monitor : ''));
  bron.onmessage = ev => {
    const d = JSON.parse(ev.data);
    K.L = d;
    clearTimeout(geenVerbinding);
    document.getElementById('verbinding').hidden = true;
    meld('live', d);
    if (d.s.wijziging !== K.wijziging) { K.wijziging = d.s.wijziging; laadState(); }
    else if (K.S && d.s.patch_versie !== K.S.status.patch_versie) laadState(true);
  };
  bron.onerror = () => {
    clearTimeout(geenVerbinding);
    geenVerbinding = setTimeout(() => { document.getElementById('verbinding').hidden = false; }, 1500);
    if (bron.readyState === EventSource.CLOSED) setTimeout(() => { bron = null; startLive(); }, 2000);
  };
}
export function zetMonitor(u) { K.monitor = u; startLive(); }

// ------------------------------------------------------------------ hulpjes
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const kloon = o => JSON.parse(JSON.stringify(o));
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const $ = (sel, el = document) => el.querySelector(sel);
export const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

export function afremmen(fn, ms) {
  let laatste = 0, timer = null, args = null;
  return (...a) => {
    args = a;
    const nu = Date.now();
    clearTimeout(timer);
    if (nu - laatste >= ms) { laatste = nu; fn(...args); }
    else timer = setTimeout(() => { laatste = Date.now(); fn(...args); }, ms - (nu - laatste));
  };
}

export function toast(tekst, fout = false) {
  const t = document.createElement('div');
  t.className = 'toast' + (fout ? ' fout' : '');
  t.textContent = tekst;
  document.getElementById('toasts').appendChild(t);
  setTimeout(() => t.remove(), fout ? 5000 : 2000);
}

// Dialoogvenster. knoppen: [{tekst, klasse, actie(dialoog) -> false om open te houden}]
export function dialoog({ titel, html = '', knoppen = [{ tekst: 'Sluiten' }], breed = false, bijOpen }) {
  const achter = document.createElement('div');
  achter.className = 'achtergrond';
  achter.innerHTML = `<div class="dialoog ${breed ? 'breed' : ''}" role="dialog" aria-modal="true">
    <h2>${esc(titel)}</h2><div class="lijf">${html}</div><div class="voet"></div></div>`;
  const d = { el: achter.querySelector('.dialoog'), lijf: achter.querySelector('.lijf'), sluit: () => { achter.remove(); document.removeEventListener('keydown', toets); } };
  const voet = achter.querySelector('.voet');
  knoppen.forEach(k => {
    const b = document.createElement('button');
    b.textContent = k.tekst; if (k.klasse) b.className = k.klasse;
    b.onclick = async () => { if (k.actie && (await k.actie(d)) === false) return; d.sluit(); };
    voet.appendChild(b);
  });
  const toets = e => {
    if (e.key === 'Escape') d.sluit();
    if (e.key === 'Enter' && e.target.tagName === 'INPUT' && knoppen.length) voet.lastChild.click();
  };
  document.addEventListener('keydown', toets);
  achter.addEventListener('pointerdown', e => { if (e.target === achter) d.sluit(); });
  document.body.appendChild(achter);
  if (bijOpen) bijOpen(d);
  const eerste = d.lijf.querySelector('input:not([type=checkbox]), select, textarea'); if (eerste) eerste.focus();
  return d;
}

export function vraag(tekst, jaTekst = 'OK', gevaar = false) {
  return new Promise(ok => dialoog({
    titel: tekst, knoppen: [{ tekst: 'Annuleren', actie: () => ok(false) },
      { tekst: jaTekst, klasse: gevaar ? 'gevaar aan' : 'primair', actie: () => ok(true) }],
  }));
}

export function invoer(titel, standaard = '', uitleg = '') {
  return new Promise(ok => dialoog({
    titel, html: `${uitleg ? `<p class="hint">${esc(uitleg)}</p>` : ''}<input id="dlgInvoer" style="width:100%" value="${esc(standaard)}">`,
    knoppen: [{ tekst: 'Annuleren', actie: () => ok(null) },
      { tekst: 'OK', klasse: 'primair', actie: d => ok(d.lijf.querySelector('#dlgInvoer').value.trim()) }],
  }));
}

export function download(naam, tekst, soort = 'application/json') {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([tekst], { type: soort }));
  a.download = naam;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export function kiesBestand(accept) {
  return new Promise(ok => {
    const i = document.createElement('input');
    i.type = 'file'; i.accept = accept;
    i.onchange = () => {
      const f = i.files[0]; if (!f) return ok(null);
      const r = new FileReader();
      r.onload = () => ok({ naam: f.name, inhoud: r.result });
      r.readAsText(f);
    };
    i.click();
  });
}

// ------------------------------------------------------------------ pincode
let pinOpen = false;
export function toonPin() {
  if (pinOpen) return;
  pinOpen = true;
  const el = document.createElement('div');
  el.className = 'pinscherm';
  el.innerHTML = `<form class="blok"><h2>Pincode</h2><p class="hint">Deze DMXDesk is beveiligd. Vul de pincode in.</p>
    <input type="password" inputmode="numeric" autocomplete="current-password" maxlength="8" id="pinVeld">
    <button class="primair" style="width:100%">Openen</button><p class="hint fout" id="pinFout"></p></form>`;
  document.body.appendChild(el);
  el.querySelector('input').focus();
  el.querySelector('form').onsubmit = async ev => {
    ev.preventDefault();
    const r = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: el.querySelector('input').value }) });
    if (r.ok) location.reload();
    else el.querySelector('#pinFout').textContent = 'Verkeerde pincode';
  };
}

// ------------------------------------------------------------------ show-hulpjes
export function adresBereik(f, S = K.S) {
  const p = S.profielen[f.profiel]; const n = p ? p.kanalen.length : 1;
  return [Number(f.adres), Number(f.adres) + n - 1];
}
export function overlapt(lijst, i, S = K.S) {
  const [a, b] = adresBereik(lijst[i], S);
  if (b > 512) return 'past niet in de universe';
  const ander = lijst.find((g, j) => j !== i && Number(g.universe) === Number(lijst[i].universe) &&
    (() => { const [c, d] = adresBereik(g, S); return a <= d && c <= b; })());
  return ander ? 'overlapt met ' + ander.naam : '';
}
export function vrijAdres(lijst, universe, aantal, S = K.S) {
  // eerste plek in deze universe waar 'aantal' kanalen vrij zijn
  const bezet = lijst.filter(f => Number(f.universe) === Number(universe)).map(f => adresBereik(f, S)).sort((a, b) => a[0] - b[0]);
  let adres = 1;
  for (const [a, b] of bezet) { if (adres + aantal - 1 < a) break; adres = Math.max(adres, b + 1); }
  return adres + aantal - 1 <= 512 ? adres : null;
}
export function sceneKleur(sc) { return sc && sc.kleur ? sc.kleur : ''; }
export function tijdNaam(s) { return s === 'seconden' ? 's' : 'beats'; }

// ------------------------------------------------------------------ vasthoudknoppen
// STROBE / SMOKE / BLINDER werken alleen zolang je ze vasthoudt. Zolang er iets ingedrukt is,
// sturen we elke 250 ms een bericht; de server laat na 0,7 s zonder bericht vanzelf los.
const houders = new Map();   // bron (vinger, toets) -> soort
let houdTimer = null;
function stuurHold() {
  const soorten = new Set(houders.values());
  fetch('/api/hold', { method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
    body: JSON.stringify({ smoke: soorten.has('smoke'), strobe: soorten.has('strobe'), blinder: soorten.has('blinder') }) }).catch(() => {});
  meld('houd', soorten);
}
export function houd(bron, soort, aan) {
  const was = houders.get(bron);
  if (aan) houders.set(bron, soort); else houders.delete(bron);
  if (was === houders.get(bron)) return;
  stuurHold();
  if (houders.size && !houdTimer) {
    houdTimer = setInterval(() => { stuurHold(); if (!houders.size) { clearInterval(houdTimer); houdTimer = null; } }, 250);
  }
}
export function lasAlles() { if (houders.size) { houders.clear(); stuurHold(); } }
export function houdKnop(el, soort) {
  // koppelt een knop aan een vasthoud-soort (meerdere vingers tegelijk mag)
  el.addEventListener('pointerdown', e => {
    e.preventDefault(); el.setPointerCapture(e.pointerId);
    houd('p' + e.pointerId, soort, true);
    if (navigator.vibrate) navigator.vibrate(15);
  });
  const los = e => houd('p' + e.pointerId, soort, false);
  el.addEventListener('pointerup', los); el.addEventListener('pointercancel', los); el.addEventListener('lostpointercapture', los);
  el.addEventListener('contextmenu', e => e.preventDefault());
}
