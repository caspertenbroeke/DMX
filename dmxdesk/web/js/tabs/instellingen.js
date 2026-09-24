// Instellingen: show bewaren/delen, telefoon koppelen, pincode, MIDI, sneltoetsen, systeem.
import { K, api, doe, esc, $, toast, vraag, invoer, laadState, kiesBestand, download } from '../kern.js';

let midiApparaten = null;
const ACTIES = [
  ['scene', 'Scène laden', 'scene'], ['scene_los', 'Scène loslaten'], ['cue', 'Cuelijst start/stop', 'cue'],
  ['cue_volgende', 'Cue volgende'], ['cue_vorige', 'Cue vorige'], ['hold', 'Vasthouden', 'hold'], ['blackout', 'Blackout aan/uit'],
  ['freeze', 'Freeze aan/uit'], ['auto', 'Auto-show aan/uit'], ['tap', 'Tap tempo'], ['tempo', 'Tempo-factor', 'tempo'],
  ['opbouw', 'OPBOUW aan/uit (tot DROP)'], ['drop', 'DROP'],
  ['master', 'Master (fader)'], ['groep', 'Groep (fader)', 'groep'], ['fader', 'Macro-fader', 'fader'],
];
const TOETSEN = [['Spatie', 'Tap tempo'], ['B', 'Blackout aan/uit'], ['F', 'Freeze (effecten stilzetten)'], ['A', 'Auto-show aan/uit'],
  ['S (vasthouden)', 'Strobe'], ['R (vasthouden)', 'Rook'], ['W (vasthouden)', 'Blinder (alles wit)'], ['1 … 9, 0', 'Scène 1 t/m 10'],
  ['Esc', 'Scène loslaten'], ['← / →', 'Vorige / volgende cue'], ['O', 'OPBOUW aan/uit (tot DROP)'], ['D', 'DROP']];

function argOpties(soort) {
  const S = K.S;
  if (soort === 'scene') return Object.keys(S.scenes).map(n => [n, n]);
  if (soort === 'cue') return Object.keys(S.cuelijsten).map(n => [n, n]);
  if (soort === 'hold') return [['strobe', 'Strobe'], ['smoke', 'Rook'], ['blinder', 'Blinder']];
  if (soort === 'groep') return Object.keys(S.show.groepen).map(n => [n, n]);
  if (soort === 'fader') return S.faders.map(f => [f.id, f.naam]);
  if (soort === 'tempo') return [[0.5, '½×'], [1, '1×'], [2, '2×']];
  return [];
}
function actieNaam(k) {
  const a = ACTIES.find(x => x[0] === k.actie);
  const arg = k.arg !== null && k.arg !== undefined ? ': ' + (k.actie === 'fader' ? (K.S.faders.find(f => f.id === k.arg)?.naam || k.arg) : k.arg) : '';
  return (a ? a[1] : k.actie) + arg;
}

function midiBlok() {
  const S = K.S, st = (K.L.s || S.status).midi || {};
  const koppelingen = Object.entries(S.midi.koppelingen || {});
  if (!midiApparaten) return '<p class="hint">MIDI-apparaten zoeken…</p>';
  if (!midiApparaten.beschikbaar) return '<p class="hint">MIDI is niet beschikbaar op deze computer (mido/python-rtmidi ontbreekt).</p>';
  return `<div class="rij"><label>Controller</label><select id="miApparaat" style="flex:1"><option value="">– geen –</option>
      ${[...new Set([...midiApparaten.apparaten, S.midi.apparaat].filter(Boolean))].map(n => `<option ${n === S.midi.apparaat ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
      <button class="stil" id="miZoek">↻</button></div>
    <p class="hint" id="miStatus">${st.fout ? `<span class="fout">${esc(st.fout)}</span>` : st.apparaat ? '✓ verbonden' : ''}
      ${st.laatste ? ` · laatst: <code>${esc(st.laatste.sleutel)}</code>` : ''}</p>
    <h3>Nieuwe koppeling</h3>
    <div class="rij"><select id="miActie">${ACTIES.map(([k, t]) => `<option value="${k}">${esc(t)}</option>`).join('')}</select>
      <select id="miArg"></select><button class="primair" id="miLeer">Leren</button></div>
    <p class="hint" id="miLeerTekst">${st.leren ? '⏳ Druk nu op een knop of beweeg een fader op je controller…' : 'Kies een actie, klik Leren en druk dan op de knop van je controller.'}</p>
    ${koppelingen.length ? `<table><tr><th>MIDI</th><th>Actie</th><th></th></tr>${koppelingen.map(([s, k]) => `<tr><td><code>${esc(s)}</code></td>
      <td>${esc(actieNaam(k))}</td><td style="width:40px"><button class="stil icoon" data-miweg="${esc(s)}">×</button></td></tr>`).join('')}</table>` : ''}`;
}

function teken(el) {
  const S = K.S, sys = S.systeem;
  el.innerHTML = `<div class="paginakop"><h1>Instellingen</h1></div>
  <div class="raster">
    <div class="blok"><h2>Show</h2>
      <div class="rij"><label>Naam</label><input id="inNaam" value="${esc(S.naam)}" style="flex:1"></div>
      <div class="knoppen twee"><button id="inExport">Show exporteren…</button><button id="inImport">Show importeren…</button>
        <button id="inLeeg">Nieuwe lege show</button><button id="inDemo">Voorbeeldshow laden</button></div>
      ${sys.show_bestand ? `<p class="hint">Wordt automatisch bewaard in <code>${esc(sys.show_bestand)}</code></p>` : ''}
      <p class="hint">Exporteren maakt een bestand dat je kunt bewaren of met iemand delen. Importeren vervangt de huidige show (je uitgangen blijven).</p>
    </div>
    <div class="blok"><h2>Telefoon of tablet verbinden</h2>
      <p class="hint">Zet je telefoon op <b>hetzelfde wifi-netwerk</b> en open:</p>
      ${sys.adressen.length ? sys.adressen.map(a => `<p style="font-size:18px;margin:6px 0"><a href="${esc(a)}" target="_blank" rel="noopener">${esc(a)}</a></p>`).join('')
        : '<p class="hint fout">Geen netwerkverbinding gevonden.</p>'}
      ${sys.qr && sys.adressen.length ? `<img src="/api/qr?url=${encodeURIComponent(sys.adressen[0])}" alt="QR-code" style="width:180px;height:180px;background:#fff;border-radius:10px;padding:6px">` : ''}
      <p class="hint">Daar staan de grote knoppen (SMOKE, STROBE, BLINDER) en je scènes. Via "Alles" kom je bij dit volledige scherm.
        Tip: "Zet op beginscherm" in je browser maakt er een app-icoontje van.</p>
    </div>
    <div class="blok"><h2>Pincode</h2>
      <p class="hint">${S.instellingen.pin ? '🔒 Er staat een pincode op. Telefoons en andere computers moeten die invullen.'
        : 'Iedereen op hetzelfde wifi-netwerk kan nu meebedienen. Met een pincode kan dat alleen als je de code weet.'}
        Op deze computer zelf is nooit een pincode nodig.</p>
      <div class="rij"><input id="inPin" type="password" inputmode="numeric" maxlength="8" placeholder="4 tot 8 cijfers" style="width:160px">
        <button id="inPinZet" class="primair">${S.instellingen.pin ? 'Wijzigen' : 'Instellen'}</button>
        ${S.instellingen.pin ? '<button id="inPinWeg" class="gevaar">Verwijderen</button>' : ''}</div>
    </div>
    <div class="blok"><h2>MIDI-controller</h2><div id="inMidi">${midiBlok()}</div></div>
    <div class="blok"><h2>Sneltoetsen</h2><table>${TOETSEN.map(([t, u]) => `<tr><td style="width:140px"><code>${t}</code></td><td>${u}</td></tr>`).join('')}</table></div>
    <div class="blok"><h2>Systeem</h2>
      <p class="hint">DMXDesk ${esc(S.versie)} · ${esc(sys.platform)} · poort ${sys.poort}</p>
      ${sys.knoppen ? `<p class="hint">Zet de computer (Raspberry Pi) altijd hiermee uit voordat je de stroom eraf haalt, anders kan de SD-kaart beschadigen.</p>
        <div class="knoppen twee"><button id="inHerstart">Herstarten</button><button class="gevaar" id="inUit">⏻ Uitzetten</button></div>` : ''}
      ${sys.lokaal ? '<div class="knoppen twee" style="margin-top:8px"><button class="gevaar" id="inAfsluiten">DMXDesk afsluiten</button></div>' : ''}
      <h3>Lampenbibliotheek</h3>
      <p class="hint">${S.bibliotheek.aantal} lampen van ${S.bibliotheek.fabrikanten} merken, uit de
        <a href="https://open-fixture-library.org" target="_blank" rel="noopener">Open Fixture Library</a> (MIT-licentie)${S.bibliotheek.datum ? ', bijgewerkt ' + esc(S.bibliotheek.datum) : ''}.</p>
    </div>
  </div>`;
  argKiezen();
}

function argKiezen() {
  const a = $('#miActie'), s = $('#miArg'); if (!a || !s) return;
  const opties = argOpties(a.value);
  s.hidden = !opties.length;
  s.innerHTML = opties.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
}

async function laadMidi() {
  try { midiApparaten = await api('/api/midi/apparaten'); } catch (e) { midiApparaten = { beschikbaar: false, apparaten: [] }; }
  if ($('#inMidi')) { $('#inMidi').innerHTML = midiBlok(); argKiezen(); }
}

async function importeer() {
  const b = await kiesBestand('.json');
  if (!b) return;
  let show;
  try { show = JSON.parse(b.inhoud); } catch (e) { return toast('Dit is geen geldig showbestand', true); }
  if (!(await vraag(`Show "${show.naam || b.naam}" importeren? De huidige show wordt vervangen (exporteer hem eerst als je hem wilt bewaren).`, 'Importeren', true))) return;
  if (await doe('/api/import', { show }, 'Show geïmporteerd')) laadState(true);
}

async function systeem(actie) {
  const tekst = actie === 'uitzetten' ? 'Computer uitzetten? Muziek en licht stoppen dan.' : 'Computer herstarten? Muziek en licht zijn ongeveer een minuut weg.';
  if (!(await vraag(tekst, actie === 'uitzetten' ? 'Uitzetten' : 'Herstarten', true))) return;
  if (!(await doe('/api/systeem', { actie }))) return;
  $('#inhoud').innerHTML = `<div class="blok" style="max-width:560px;margin:40px auto;text-align:center"><h2>${actie === 'uitzetten' ? 'De computer gaat uit' : 'De computer herstart'}</h2>
    ${actie === 'uitzetten' ? '<p style="font-size:16px">Wacht tot het <b>groene lampje</b> niet meer knippert (ongeveer 20 seconden). Daarna mag de stekker eruit.</p>'
      : '<p style="font-size:16px">Over ongeveer een minuut is alles terug. Herlaad dan deze pagina.</p>'}</div>`;
}

export default {
  id: 'instellingen', titel: 'Instellingen',
  icoon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  teken(el) {
    teken(el);
    if (!midiApparaten) laadMidi();
    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.id === 'inExport') {
        try {
          const r = await fetch('/api/export'); const t = await r.text();
          download(`${(K.S.naam || 'show').replace(/[^\w\- ]+/g, '_')}.dmxshow.json`, t);
        } catch (x) { toast(x.message, true); }
      } else if (b.id === 'inImport') importeer();
      else if (b.id === 'inLeeg') {
        if (await vraag('Nieuwe lege show beginnen? Alle lampen, scènes en cuelijsten gaan weg (exporteer eerst als je ze wilt bewaren).', 'Leeg beginnen', true))
          if (await doe('/api/import', { show: { versie: 2, naam: 'Nieuwe show', fixtures: [], scenes: {}, cuelijsten: {} } }, 'Nieuwe show')) laadState(true);
      } else if (b.id === 'inDemo') {
        if (await vraag('De voorbeeldshow laden? De huidige show wordt vervangen.', 'Laden', true))
          if (await doe('/api/import', { show: { versie: 2, naam: 'Voorbeeldshow', show: {} } }, 'Voorbeeldshow geladen')) laadState(true);
      } else if (b.id === 'inPinZet') {
        const pin = $('#inPin').value.trim();
        if (await doe('/api/pin', { pin }, 'Pincode ingesteld')) laadState();
      } else if (b.id === 'inPinWeg') { if (await doe('/api/pin', { pin: '' }, 'Pincode verwijderd')) laadState(); }
      else if (b.id === 'miZoek') { midiApparaten = null; $('#inMidi').innerHTML = midiBlok(); laadMidi(); }
      else if (b.id === 'miLeer') {
        const actie = $('#miActie').value, arg = $('#miArg').hidden ? null : $('#miArg').value;
        await doe('/api/midi/leer', { actie, arg: actie === 'fader' || actie === 'tempo' ? Number(arg) : arg });
      } else if (b.dataset.miweg) {
        const k = { ...K.S.midi.koppelingen }; delete k[b.dataset.miweg];
        if (await doe('/api/midi', { koppelingen: k })) laadState();
      } else if (b.id === 'inUit') systeem('uitzetten');
      else if (b.id === 'inHerstart') systeem('herstarten');
      else if (b.id === 'inAfsluiten') {
        if (await vraag('DMXDesk afsluiten? De lampen gaan uit.', 'Afsluiten', true)) {
          await doe('/api/afsluiten', {});
          document.body.innerHTML = '<div class="laden">DMXDesk is afgesloten. Je kunt dit venster sluiten.</div>';
        }
      }
    };
    el.onchange = async e => {
      const i = e.target;
      if (i.id === 'inNaam') { if (await doe('/api/naam', { naam: i.value })) laadState(); }
      else if (i.id === 'miActie') argKiezen();
      else if (i.id === 'miApparaat') { if (await doe('/api/midi', { apparaat: i.value })) laadState(); }
    };
  },
  state(el) { const a = document.activeElement; if (!(a && a.id === 'inPin')) teken(el); },
  live(L) {
    const m = L.s.midi || {};
    const t = $('#miLeerTekst'); if (t) t.textContent = m.leren ? '⏳ Druk nu op een knop of beweeg een fader op je controller…' : 'Kies een actie, klik Leren en druk dan op de knop van je controller.';
    const s = $('#miStatus');
    if (s) s.innerHTML = (m.fout ? `<span class="fout">${esc(m.fout)}</span>` : m.apparaat ? '✓ verbonden' : '') + (m.laatste ? ` · laatst: <code>${esc(m.laatste.sleutel)}</code>` : '');
  },
};
