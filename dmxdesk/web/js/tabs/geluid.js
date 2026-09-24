// Geluid: DMXDesk als Spotify-speaker, waar de beat vandaan komt (geluidskaart of de beat-luisteraar op de Pi)
// en het gelijkzetten van licht en muziek.
import { K, api, doe, esc, $, afremmen, zetShow } from '../kern.js';

let apparaten = null, uitvoer = null;
const BRONNAAM = { audio: 'Geluidskaart', connect: 'Spotify-speaker', spotify: 'Spotify (Pi)', mpd: 'Mp3/MPD (Pi)' };

async function laadUitvoer() {
  try { uitvoer = await api('/api/spotify/uitvoer'); } catch (e) { uitvoer = { beschikbaar: false, apparaten: [] }; }
  if ($('#glSpotify')) spotify();
}

function spotifyStatus(st, cfg) {
  if (!cfg.aan) return 'Uit';
  if (st.fout) return `<span class="fout">${esc(st.fout)}</span>`;
  if (!st.aan) return 'Starten…';
  if (st.vullen) return `<i class="dot half"></i> Licht klaarzetten: ${st.vooruit} van ${cfg.voorsprong} s gehoord, dan begint de muziek`;
  if (st.speelt) return `<i class="dot ok"></i> Speelt${st.nummer ? `: <b>${esc(st.nummer)}</b>` : ''} · het licht hoort nu <b>${st.vooruit} s</b> vooruit (ingesteld ${cfg.voorsprong} s)`;
  if (st.verbonden) return `<i class="dot half"></i> Verbonden met Spotify, wacht op muziek${st.nummer ? ` (laatst: ${esc(st.nummer)})` : ''}`;
  return `<i class="dot half"></i> Klaar: kies <b>${esc(cfg.naam)}</b> als speaker in de Spotify-app`;
}

function spotify() {
  const S = K.S, cfg = S.spotify, st = (K.L.s || S.status).spotify || {};
  const lijst = uitvoer ? uitvoer.apparaten : [];
  $('#glSpotify').innerHTML = !st.beschikbaar
    ? `<p class="hint">Deze installatie heeft geen ingebouwde Spotify-speaker${st.fout ? ` (${esc(st.fout)})` : ''}.</p>
       <p class="hint">Op de Raspberry Pi doet <b>raspotify</b> dit: kies in Spotify de speaker van de Pi. De muziek loopt daar ook
         4 seconden vooruit door de beat-luisteraar (zie de LEESMIJ).</p>`
    : `<div class="knoppen twee"><button data-spotify="aan" class="${cfg.aan ? 'aan' : ''}">SPEAKER AAN</button>
         <button data-spotify="uit" class="${!cfg.aan ? 'aan' : ''}">UIT</button></div>
       <p class="hint" id="glSpStatus">${spotifyStatus(st, cfg)}</p>
       <div class="rij"><label>Naam in Spotify</label><input id="glSpNaam" value="${esc(cfg.naam)}" maxlength="40" style="flex:1"></div>
       <div class="rij"><label>Afspelen via</label><select id="glSpUit" style="flex:1">
         <option value="">Standaard-luidspreker van het systeem</option>
         ${lijst.map(d => `<option value="${esc(d.naam)}" ${d.naam === cfg.apparaat ? 'selected' : ''}>${esc(d.naam)}</option>`).join('')}
         ${cfg.apparaat && !lijst.some(d => d.naam === cfg.apparaat) ? `<option value="${esc(cfg.apparaat)}" selected>${esc(cfg.apparaat)} (niet gevonden)</option>` : ''}
       </select><button class="stil" id="glSpVernieuw" title="Opnieuw zoeken">↻</button></div>
       <div class="rij"><label>Licht vooruit</label><input type="range" min="0" max="20" step="0.5" value="${cfg.voorsprong}" id="glSpVoor">
         <span class="waarde">${cfg.voorsprong} s</span></div>
       <p class="hint">Open Spotify op je telefoon of computer (zelfde wifi), tik op het speaker-icoon en kies <b>${esc(cfg.naam)}</b>,
         net als bij Sonos. DMXDesk hoort de muziek eerst en speelt hem <b>${cfg.voorsprong} seconden later</b> af (na het kiezen van
         een nummer duurt het dus even voor je iets hoort): zo weet de lichtshow vooraf
         waar elke beat en drop valt en bouwt hij op naar de drop. Pauze, volgende nummer en volume werken toch meteen,
         in Spotify én met de speler onderin (of op je telefoon: tabblad Muziek). Spotify Premium is nodig (geldt voor elke Spotify-speaker).
         ${S.systeem.platform === 'win32' ? 'Windows vraagt de eerste keer of <b>dmxdesk-spotify</b> het netwerk mag gebruiken: kies <b>Toestaan</b> (privé-netwerk).' : ''}</p>`;
}

async function laadApparaten() {
  try { apparaten = await api('/api/audio/apparaten'); } catch (e) { apparaten = { beschikbaar: false, apparaten: [] }; }
  if ($('#glKaart')) kaart();
}

function kaart() {
  const S = K.S, a = S.audio, st = (K.L.s || S.status).audio || {};
  const lijst = apparaten ? apparaten.apparaten : [];
  $('#glKaart').innerHTML = !apparaten ? '<p class="hint">Geluidsapparaten zoeken…</p>' : !apparaten.beschikbaar
    ? `<p class="hint fout">Geluidskaart niet beschikbaar op deze computer (het onderdeel sounddevice/PortAudio ontbreekt).</p>
       <p class="hint">Op een Raspberry Pi gebruik je de beat-luisteraar voor Spotify en MPD (zie hieronder).</p>`
    : `<div class="knoppen twee"><button data-audio="aan" class="${a.aan ? 'aan' : ''}">LUISTEREN AAN</button>
         <button data-audio="uit" class="${!a.aan ? 'aan' : ''}">UIT</button></div>
       <div class="rij"><label>Invoer</label><select id="glApparaat" style="flex:1">
         <option value="">Standaard-invoer van het systeem</option>
         ${lijst.map(d => `<option value="${esc(d.naam)}" ${d.naam === a.apparaat ? 'selected' : ''}>${d.loopback ? '🔊 ' : '🎤 '}${esc(d.naam)}</option>`).join('')}
       </select><button class="stil" id="glVernieuw" title="Opnieuw zoeken">↻</button></div>
       <div class="meter"><i id="glNiveau"></i></div>
       <p class="hint" id="glStatus">${st.fout ? `<span class="fout">${esc(st.fout)}</span>` : a.aan ? 'Luistert…' : 'Uit'}</p>
       <p class="hint">🎤 = microfoon of line-in (bijvoorbeeld de uitgang van je mengpaneel). 🔊 = het geluid van de computer zelf.
         Geluid van de computer zelf: kies op Windows een apparaat met <b>[Loopback]</b> of <b>Stereomix</b>; op de Mac installeer je
         het gratis <b>BlackHole</b>; op Linux kies je met pavucontrol <b>Monitor of …</b> als opname.</p>`;
}

function luisterTekst(s) {
  const bronnen = Object.entries(s.luister || {});
  if (!bronnen.length) return '<p class="hint">Nog niets gehoord. Zet de geluidskaart aan, of start de beat-luisteraar op de Pi.</p>';
  return bronnen.map(([b, i]) => `<div class="rij" style="margin:4px 0"><i class="dot ${i.muziek ? (i.hoort_beat ? 'ok' : 'half') : ''}"></i>
    <b style="width:140px">${esc(BRONNAAM[b] || b)}</b><span class="hint" style="margin:0">${!i.muziek ? 'hoort geen muziek'
      : `${i.dubbel ? Math.round(i.bpm * 20) / 10 : i.bpm} BPM${i.dubbel ? ' (snel nummer, ×2)' : ''} · ${i.hoort_beat ? '✓ beat gevonden' : 'zoekt de beat…'}`
        + (i.noot ? ` · melodie ${i.noot}` : '') + (i.energie !== null && i.energie !== undefined ? ` · energie ${Math.round(i.energie * 100)}%` : '')}</span></div>`).join('')
    + (s.beat_auto ? '' : '<p class="hint">BPM staat op handmatig: de gehoorde beat wordt niet gebruikt.</p>');
}

const stuurSchuif = afremmen((p, v) => zetShow(p, v, false), 100);
const schuif = (p, label, waarde, min, max) =>
  `<div class="rij"><label>${label}</label><input type="range" min="${min}" max="${max}" value="${waarde}" data-set="${p}"><span class="waarde">${waarde}</span></div>`;

function teken(el) {
  const s = K.S.show, b = s.beat;
  el.innerHTML = `<div class="paginakop"><h1>Geluid</h1><span class="hint">DMXDesk luistert mee en zet het licht op de beat.</span></div>
  <div class="raster">
    <div class="blok"><h2>Spotify-speaker</h2><div id="glSpotify"></div></div>
    <div class="blok"><h2>Geluidskaart van deze computer</h2><div id="glKaart"></div></div>
    <div class="blok"><h2>Wat DMXDesk hoort</h2><div id="glLuister">${luisterTekst(K.L.s || K.S.status)}</div>
      <h3>BPM</h3>
      <div class="knoppen twee"><button data-set="beat.auto" data-val="true" class="${b.auto ? 'aan' : ''}">♪ AUTOMATISCH</button>
        <button data-set="beat.auto" data-val="false" class="${!b.auto ? 'aan' : ''}">HANDMATIG (TAP)</button></div>
      <div class="rij"><label>Snelle nummers</label><button data-set="beat.snel_herkennen" data-val="${!b.snel_herkennen}" class="${b.snel_herkennen ? 'aan' : ''}" style="flex:1">
        ${b.snel_herkennen ? 'Herkennen (×2 bij kick tussen de beats): AAN' : 'Herkennen: UIT (altijd het rustige tempo)'}</button></div>
      <div class="rij"><label>BPM tussen</label><input type="number" min="40" max="240" value="${b.bpm_min}" data-set="beat.bpm_min">
        <span class="hint">en</span><input type="number" min="40" max="240" value="${b.bpm_max}" data-set="beat.bpm_max"></div>
    </div>
    <div class="blok"><h2>Licht gelijk zetten met de muziek</h2>
      <p class="hint">Loopt het licht vóór op de muziek? Schuif naar rechts. Loopt het achter? Naar links. (milliseconden)</p>
      ${schuif('beat.vertraging_connect', 'Spotify-speaker', b.vertraging_connect, -300, 1200)}
      ${schuif('beat.vertraging_audio', 'Geluidskaart', b.vertraging_audio, -300, 1200)}
      ${schuif('beat.vertraging_spotify', 'Spotify (Pi)', b.vertraging_spotify, -300, 1200)}
      ${schuif('beat.vertraging_mpd', 'Mp3/MPD (Pi)', b.vertraging_mpd, -300, 1200)}
    </div>
  </div>`;
  spotify();
  kaart();
}

const stuurSpotify = afremmen(v => doe('/api/spotify', { voorsprong: v }), 400);

export default {
  id: 'geluid', titel: 'Geluid',
  icoon: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  teken(el) {
    teken(el);
    if (apparaten === null) laadApparaten();
    if (uitvoer === null) laadUitvoer();
    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.spotify) return doe('/api/spotify', { aan: b.dataset.spotify === 'aan' });
      if (b.id === 'glSpVernieuw') { uitvoer = null; spotify(); return laadUitvoer(); }
      if (b.dataset.audio) {
        await doe('/api/audio', { aan: b.dataset.audio === 'aan', apparaat: $('#glApparaat') ? $('#glApparaat').value : K.S.audio.apparaat });
        return;
      }
      if (b.id === 'glVernieuw') { apparaten = null; kaart(); return laadApparaten(); }
      if (b.dataset.set !== undefined) { let v = b.dataset.val; try { v = JSON.parse(v); } catch (x) { /* tekst */ } return zetShow(b.dataset.set, v); }
    };
    el.oninput = e => {
      const i = e.target;
      if (i.type === 'range' && i.dataset.set) { i.nextElementSibling.textContent = i.value; stuurSchuif(i.dataset.set, Number(i.value)); }
      else if (i.id === 'glSpVoor') { i.nextElementSibling.textContent = i.value + ' s'; stuurSpotify(Number(i.value)); }
    };
    el.onchange = e => {
      const i = e.target;
      if (i.id === 'glApparaat') doe('/api/audio', { aan: K.S.audio.aan, apparaat: i.value || null });
      else if (i.id === 'glSpNaam') doe('/api/spotify', { naam: i.value });
      else if (i.id === 'glSpUit') doe('/api/spotify', { apparaat: i.value || null });
      else if (i.type === 'number' && i.dataset.set) zetShow(i.dataset.set, Number(i.value));
    };
  },
  state() { if ($('#glKaart')) { const el = $('#inhoud'); teken(el); } },
  live(L) {
    const n = $('#glNiveau'), a = L.s.luister && L.s.luister.audio;
    if (n) n.style.width = a ? Math.min(100, Math.round(Math.sqrt(a.niveau / 0.25) * 100)) + '%' : '0%';
    const li = $('#glLuister'); if (li) li.innerHTML = luisterTekst(L.s);
    const sp = $('#glSpStatus');
    if (sp && L.s.spotify) sp.innerHTML = spotifyStatus(L.s.spotify, K.S.spotify);
    const st = $('#glStatus'), au = L.s.audio;
    if (st && au) st.innerHTML = au.fout ? `<span class="fout">${esc(au.fout)}</span>` : au.aan ? `Luistert naar ${esc(au.apparaat || 'de standaard-invoer')}` : 'Uit';
  },
};
