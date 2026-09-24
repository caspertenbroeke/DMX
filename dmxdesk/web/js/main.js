// Hoofdscript: menu, kopbalk, sneltoetsen en het wisselen tussen tabbladen.
import { K, op, api, doe, laadState, startLive, $, esc, houd, lasAlles, toast, vraag, afremmen } from './kern.js';
import live from './tabs/live.js';
import effecten from './tabs/effecten.js';
import programmer from './tabs/programmer.js';
import scenes from './tabs/scenes.js';
import podium from './tabs/podium.js';
import patch from './tabs/patch.js';
import profielen from './tabs/profielen.js';
import uitgangen from './tabs/uitgangen.js';
import geluid from './tabs/geluid.js';
import monitor from './tabs/monitor.js';
import instellingen from './tabs/instellingen.js';

const TABS = [live, effecten, programmer, scenes, podium, null, patch, profielen, uitgangen, geluid, monitor, null, instellingen];
const inhoud = $('#inhoud');
let huidig = null, uitgesteld = false;

// ------------------------------------------------------------------ menu en tabbladen
function bouwMenu() {
  $('#menu').innerHTML = TABS.map(t => t ? `<button data-tab="${t.id}" title="${esc(t.titel)}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${t.icoon}</svg>
      <span>${esc(t.titel)}</span></button>` : '<div class="scheiding"></div>').join('');
  $('#menu').addEventListener('click', e => { const b = e.target.closest('[data-tab]'); if (b) gaNaar(b.dataset.tab); });
}

export async function gaNaar(id) {
  const t = TABS.find(x => x && x.id === id) || live;
  if (huidig && huidig !== t && huidig.vuil && huidig.vuil() &&
      !(await vraag('Er zijn wijzigingen die nog niet zijn opgeslagen. Toch weggaan?', 'Weggaan', true))) {
    history.replaceState(null, '', '#' + huidig.id);
    return;
  }
  if (huidig && huidig.weg) huidig.weg();
  huidig = t;
  if (location.hash !== '#' + t.id) history.replaceState(null, '', '#' + t.id);
  document.querySelectorAll('#menu button').forEach(b => b.classList.toggle('actief', b.dataset.tab === t.id));
  inhoud.innerHTML = '';
  inhoud.onclick = inhoud.oninput = inhoud.onchange = null;   // afhandeling van het vorige tabblad weghalen
  inhoud.scrollTop = 0; window.scrollTo(0, 0);
  if (K.S) t.teken(inhoud);
}

function opnieuwTekenen() {
  if (!huidig || !K.S) return;
  // niet tekenen terwijl je typt of sleept: dan zou je invoer verdwijnen
  const actief = document.activeElement;
  const typt = actief && inhoud.contains(actief) && /INPUT|TEXTAREA|SELECT/.test(actief.tagName) && actief.type !== 'range'
    && actief.type !== 'checkbox' && actief.type !== 'button';
  if (K.bezig || typt || (huidig.vuil && huidig.vuil())) { uitgesteld = true; return; }
  uitgesteld = false;
  if (huidig.state) huidig.state(inhoud); else huidig.teken(inhoud);
}
inhoud.addEventListener('focusout', () => setTimeout(() => { if (uitgesteld) opnieuwTekenen(); }, 50));
window.addEventListener('pointerup', () => { if (K.bezig) { K.bezig = false; setTimeout(() => { if (uitgesteld) opnieuwTekenen(); }, 200); } });
inhoud.addEventListener('pointerdown', e => { if (e.target.type === 'range') K.bezig = true; });

// ------------------------------------------------------------------ kopbalk
function kopState(S) {
  $('#showNaam').textContent = S.naam || '';
  document.title = `DMXDesk – ${S.naam || ''}`;
}
let beatInfo = { beat: 0, bpm: 120, t: 0 };
function kopLive(L) {
  const s = L.s;
  const uitg = Object.values(s.uitgangen || {});
  const ok = uitg.filter(u => u.ok).length;
  const dot = $('#kDmx .dot');
  dot.className = 'dot' + (uitg.length && ok === uitg.length ? ' ok' : ok ? ' half' : '');
  $('#kDmx span').textContent = !uitg.length ? 'geen uitgang' : ok === uitg.length ? `DMX ok` : `DMX ${ok}/${uitg.length}`;
  $('#kBpm').textContent = s.bpm;
  $('#kBpm').title = s.beat_auto ? 'automatisch (hoort de muziek)' : 'handmatig';
  beatInfo = { beat: s.beat, bpm: s.bpm, t: performance.now() };
  const e = Object.values(s.luister || {}).find(i => i.energie !== null && i.energie !== undefined);
  $('#kEnergie').style.width = e ? Math.round(e.energie * 100) + '%' : '0%';
  const lm = s.lichtman, klm = $('#kLm');
  klm.hidden = !lm;
  if (lm) {
    klm.textContent = lm.flits ? '💥 DROP' : lm.naam + (lm.sectie === 'opbouw' && lm.opbouw !== null ? ` ${Math.round(lm.opbouw * 100)}%` : '')
      + (lm.drop_over && lm.sectie === 'opbouw' ? ` · drop ${Math.ceil(lm.drop_over)}s` : '');
    klm.className = 'chip lm-' + lm.sectie;
  }
  const sc = $('#kScene'); sc.hidden = !s.scene; sc.textContent = s.scene ? '▶ ' + s.scene : '';
  const cue = $('#kCue'); cue.hidden = !s.cue;
  if (s.cue) cue.textContent = `${s.cue.pauze ? '⏸' : '⟳'} ${s.cue.lijst} ${s.cue.stap + 1}/${s.cue.aantal}`;
  const pr = $('#kProg'); pr.hidden = !s.programmer; pr.textContent = `Programmer: ${s.programmer}`;
  const holds = ['strobe', 'smoke', 'blinder'].filter(h => s[h]);
  const kh = $('#kHold'); kh.hidden = !holds.length; kh.textContent = holds.join(' + ').toUpperCase();
  $('#kBlackout').classList.toggle('aan', !!s.blackout);
  $('#kFreeze').classList.toggle('blauw', true);
  $('#kFreeze').classList.toggle('aan', !!s.bevroren);
}
function beatLamp() {
  const b = beatInfo.beat + (performance.now() - beatInfo.t) / 1000 * beatInfo.bpm / 60;
  $('#kBeat').classList.toggle('aan', (b % 1 + 1) % 1 < 0.18);
  requestAnimationFrame(beatLamp);
}
$('#kTap').onclick = () => doe('/api/tap', {});
$('#kBlackout').onclick = () => doe('/api/actie', { soort: 'blackout' });
$('#kFreeze').onclick = () => doe('/api/actie', { soort: 'freeze' });
document.querySelectorAll('#kop [data-ga]').forEach(b => b.onclick = () => gaNaar(b.dataset.ga));

// ------------------------------------------------------------------ sneltoetsen
const HOUD_TOETSEN = { s: 'strobe', r: 'smoke', w: 'blinder' };
function typtErgens(e) {
  const t = e.target;
  return t && (/INPUT|TEXTAREA|SELECT/.test(t.tagName) && !['range', 'checkbox', 'button'].includes(t.type) || t.isContentEditable);
}
document.addEventListener('keydown', e => {
  if (typtErgens(e) || e.ctrlKey || e.metaKey || e.altKey || document.querySelector('.achtergrond')) return;
  const k = e.key.toLowerCase();
  if (HOUD_TOETSEN[k]) { e.preventDefault(); if (!e.repeat) houd('toets-' + k, HOUD_TOETSEN[k], true); return; }
  if (e.repeat) return;
  const scenes = K.S ? Object.keys(K.S.scenes) : [];
  if (k === ' ') { e.preventDefault(); doe('/api/tap', {}); }
  else if (k === 'b') doe('/api/actie', { soort: 'blackout' });
  else if (k === 'f') doe('/api/actie', { soort: 'freeze' });
  else if (k === 'a') doe('/api/actie', { soort: 'auto' });
  else if (k === 'escape') doe('/api/actie', { soort: 'scene_los' });
  else if (k === 'arrowright' && K.L.s && K.L.s.cue) doe('/api/cue', { actie: 'volgende' });
  else if (k === 'arrowleft' && K.L.s && K.L.s.cue) doe('/api/cue', { actie: 'vorige' });
  else if (/^[0-9]$/.test(k)) {
    const naam = scenes[(Number(k) + 9) % 10];
    if (naam) doe('/api/scene', { actie: 'laden', naam });
  }
});
document.addEventListener('keyup', e => { const k = e.key.toLowerCase(); if (HOUD_TOETSEN[k]) houd('toets-' + k, HOUD_TOETSEN[k], false); });
window.addEventListener('blur', lasAlles);
document.addEventListener('visibilitychange', () => { if (document.hidden) lasAlles(); });

// ------------------------------------------------------------------ start
op('state', S => { kopState(S); opnieuwTekenen(); });
op('live', L => { kopLive(L); spelerLive(L); if (huidig && huidig.live) huidig.live(L); });

// ------------------------------------------------------------------ speler (Spotify-speaker)
const tijd = ms => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
let sp = null, spKlok = 0, volumeBezig = 0;
function spelerLive(L) {
  const st = L.s.spotify, balk = $('#speler');
  const zien = !!(st && st.aan && (st.verbonden || (st.speler && st.speler.naam)));
  balk.hidden = !zien; document.body.classList.toggle('met-speler', zien);
  if (!zien) { sp = null; return; }
  sp = st.speler; spKlok = L.s.tijd - Date.now() / 1000;   // verschil tussen de klok van DMXDesk en deze
  $('#spNaam').textContent = sp.naam || (st.verbonden ? 'Kies een nummer in Spotify' : '–');
  $('#spArtiest').textContent = (sp.artiesten || []).join(', ') + (sp.bediening ? ` · via ${sp.bediening}` : '');
  const hoes = $('#spHoes'), url = sp.hoes || '';
  if (hoes.dataset.url !== url) { hoes.dataset.url = url; hoes.style.backgroundImage = url ? `url("${url}")` : ''; }
  $('#spPlay').textContent = sp.speelt ? '⏸' : '▶';
  if (Date.now() - volumeBezig > 1500) $('#spVolume').value = sp.volume;
}
setInterval(() => {                                        // voortgangsbalk soepel laten lopen
  if (!sp || !sp.duur) return;
  const pos = sp.pos + (sp.speelt ? (Date.now() / 1000 + spKlok - sp.pos_t) * 1000 : 0);
  $('#spPos').textContent = tijd(Math.min(pos, sp.duur)); $('#spDuur').textContent = tijd(sp.duur);
  $('#spBalk').style.width = Math.min(100, pos / sp.duur * 100) + '%';
}, 250);
const speler = (actie, waarde) => api('/api/speler', waarde === undefined ? { actie } : { actie, waarde }).catch(e => toast(e.message, true));
$('#spVorige').onclick = () => speler('prev');
$('#spVolgende').onclick = () => speler('next');
$('#spPlay').onclick = () => {
  const speelt = !!(sp && sp.speelt);
  if (sp) { sp.speelt = !speelt; $('#spPlay').textContent = sp.speelt ? '⏸' : '▶'; }
  speler(speelt ? 'pause' : 'play');
};
const stuurVolume = afremmen(v => speler('volume', v), 120);
$('#spVolume').oninput = e => { volumeBezig = Date.now(); stuurVolume(Number(e.target.value)); };
bouwMenu();
(async () => {
  try { await api('/api/info'); } catch (e) { /* geen verbinding: live probeert het opnieuw */ }
  await laadState();
  if (!K.S) { inhoud.innerHTML = '<div class="laden">Geen verbinding met DMXDesk.</div>'; }
  gaNaar(location.hash.slice(1) || 'live');
  startLive();
  requestAnimationFrame(beatLamp);
})();
window.addEventListener('hashchange', () => { const id = location.hash.slice(1); if (!huidig || id !== huidig.id) gaNaar(id); });
window.dmxdesk = { K, gaNaar, toast };
