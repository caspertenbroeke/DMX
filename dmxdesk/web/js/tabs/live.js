// Live: tijdens de show. Podium, scènes, cuelijsten, vasthoudknoppen en faders.
import { K, api, doe, esc, $, $$, afremmen, houdKnop, op } from '../kern.js';
import { Podium } from '../podium.js';

const KLEUREN = ['#ff0000', '#ff6600', '#ffcc00', '#00ff00', '#00ffff', '#0000ff', '#8800ff', '#ff00ff', '#ffffff'];
const SNEL_INT = [['aan', 'Aan'], ['chase', 'Chase'], ['puls', 'Puls'], ['flits', 'Flits'], ['sparkle', 'Sparkle'], ['golf', 'Golf']];
let podium = null, houdAf = null;

const stuurFader = afremmen((soort, id, w) => {
  if (soort === 'master') api('/api/show', { master: w }).catch(() => {});
  else if (soort === 'groep') api('/api/show', { groepen: { [id]: w } }).catch(() => {});
  else api('/api/fader', { id: Number(id), waarde: w }).catch(() => {});
}, 60);

function fader(soort, id, naam, waarde, klasse = '') {
  return `<div class="fader ${klasse}"><b>${Math.round(waarde)}</b>
    <input type="range" min="0" max="100" value="${waarde}" data-fader="${soort}" data-id="${esc(id)}" aria-label="${esc(naam)}">
    <span title="${esc(naam)}">${esc(naam)}</span></div>`;
}

const LICHT = new Set(['dimmer', 'red', 'green', 'blue', 'white', 'amber', 'uv', 'cyan', 'magenta', 'yellow', 'schakelaar']);
function metLicht(groep) {
  // een groepsfader dimt het licht; voor bijvoorbeeld alleen rookmachines heeft hij geen zin
  return K.S.fixtures.some(f => f.groep === groep && (K.S.profielen[f.profiel]?.kanalen || []).some(k => LICHT.has(k.functie)));
}

function delen() {
  const S = K.S, s = S.show, st = K.L.s || S.status;
  const scenes = Object.entries(S.scenes);
  const lijsten = Object.entries(S.cuelijsten);
  $('#lvScenes').innerHTML = scenes.length ? `<div class="scenes">${scenes.map(([n, sc], i) => `
      <button data-scene="${esc(n)}" style="${sc.kleur ? `--kleur:${sc.kleur}` : ''}" class="${st.scene === n ? 'aan' : ''}">
        <span>${esc(n)}</span><small>${[sc.effecten ? 'effecten' : '', Object.keys(sc.vast).length ? Object.keys(sc.vast).length + ' lampen' : '',
          sc.fade ? sc.fade + ' s' : ''].filter(Boolean).join(' · ')}</small>${i < 10 ? `<kbd>${(i + 1) % 10}</kbd>` : ''}</button>`).join('')}</div>`
    : '<div class="leeg">Nog geen scènes. Maak een look (tabblad Effecten of Programmer) en sla hem op als scène.</div>';
  $('#lvCues').innerHTML = lijsten.length ? lijsten.map(([n, cl]) => {
    const actief = st.cue && st.cue.lijst === n;
    return `<div class="cuerij ${actief ? 'aan' : ''}">
      <button class="${actief ? 'aan' : ''}" data-cue="${esc(n)}" title="${actief ? 'Stoppen' : 'Starten'}">${actief ? '■' : '▶'}</button>
      <span class="naam">${esc(n)}</span>
      <span class="stapjes">${cl.stappen.slice(0, 24).map((_, i) => `<i class="${actief && st.cue.stap === i ? 'aan' : ''}"></i>`).join('')}</span>
      ${actief ? `<button class="stil icoon" data-cueactie="vorige" title="Vorige (←)">⏮</button>
        <button class="stil icoon" data-cueactie="pauze" title="Pauze">${st.cue.pauze ? '▶' : '⏸'}</button>
        <button class="stil icoon" data-cueactie="volgende" title="Volgende (→)">⏭</button>` : ''}
    </div>`; }).join('') : '<p class="hint">Nog geen cuelijsten. Die maak je in het tabblad Scènes.</p>';
  $('#lvSnel').innerHTML = `
    <div class="knoppen drie">
      <button data-actie="auto" class="${s.auto.aan ? 'aan' : ''}">AUTO-SHOW</button>
      <button data-actie="freeze" class="blauw ${st.bevroren ? 'aan' : ''}">FREEZE</button>
      <button data-actie="blackout" class="gevaar ${s.blackout ? 'aan' : ''}">BLACKOUT</button>
    </div>
    <h3>Tempo</h3>
    <div class="knoppen" style="grid-template-columns:repeat(5,1fr)">
      ${[[0.25, '¼×'], [0.5, '½×'], [1, '1×'], [2, '2×'], [4, '4×']].map(([f, t]) =>
        `<button data-tempo="${f}" class="${Number(s.tempo_factor) === f ? 'aan' : ''}">${t}</button>`).join('')}
    </div>
    <h3>Kleur</h3>
    <div class="swatches">${KLEUREN.map(c => `<button class="swatch ${s.kleur.modus === 'vast' && s.kleur.palet[0] === c && s.kleur.palet.length === 1 ? 'aan' : ''}"
      style="background:${c}" data-snelkleur="${c}" title="Alles ${c}"></button>`).join('')}
      <button class="swatch" style="background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red)" data-regenboog title="Regenboog"></button></div>
    <h3>Intensiteit</h3>
    <div class="knoppen drie">${SNEL_INT.map(([m, t]) => `<button data-int="${m}" class="${s.intensiteit.modus === m ? 'aan' : ''}">${t}</button>`).join('')}</div>`;
  const lookProfielen = Object.entries(S.profielen).filter(([pid, p]) => p.looks && p.looks.length && S.fixtures.some(f => f.profiel === pid));
  $('#lvLooks').parentElement.hidden = !lookProfielen.length;
  $('#lvLooks').innerHTML = `<div class="knoppen drie" style="margin-bottom:8px">
      <button data-lookmodus="uit" class="${s.looks.modus === 'uit' ? 'aan' : ''}">Uit</button>
      <button data-lookmodus="wissel" class="${s.looks.modus === 'wissel' ? 'aan' : ''}">Wissel op de beat</button>
      <button data-lookmodus="vast" class="${s.looks.modus === 'vast' ? 'aan' : ''}">Vaste look</button></div>`
    + lookProfielen.map(([pid, p]) => `${lookProfielen.length > 1 ? `<h3>${esc(p.naam)}</h3>` : ''}<div class="knoppen">
      ${p.looks.map((l, i) => `<button data-look="${esc(pid)}" data-idx="${i}" class="${s.looks.modus === 'vast' && (s.looks.keuze[pid] || 0) === i ? 'aan' : ''}">${esc(l.naam)}</button>`).join('')}</div>`).join('');
  $('#lvFaders').innerHTML = fader('master', '', 'MASTER', s.master, 'master')
    + Object.entries(s.groepen).filter(([g]) => metLicht(g)).map(([g, v]) => fader('groep', g, g, v)).join('')
    + S.faders.map(f => fader('fader', f.id, f.naam, f.waarde)).join('');
}

function liveBijwerken(L) {
  if (podium) podium.teken();
  const st = L.s;
  $$('#lvScenes [data-scene]').forEach(b => b.classList.toggle('aan', st.scene === b.dataset.scene));
  for (const soort of ['strobe', 'smoke', 'blinder']) {
    const b = document.querySelector(`.houd.${soort}`);
    if (b && !b.matches(':active')) b.classList.toggle('aan', !!st[soort]);
  }
  const cue = st.cue ? `${st.cue.lijst}|${st.cue.stap}|${st.cue.pauze}` : '';
  if (cue !== liveBijwerken.cue && !K.bezig) { liveBijwerken.cue = cue; if (K.S) delen(); }
}

export default {
  id: 'live', titel: 'Live',
  icoon: '<circle cx="12" cy="12" r="3"/><path d="M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7"/>',
  teken(el) {
    el.innerHTML = `<div class="live">
      <div class="stapel">
        <div id="lvPodium"></div>
        <div class="blok"><div class="paginakop" style="margin:0 0 10px"><h2 style="margin:0">Scènes</h2><span class="vul"></span>
          <button class="stil" id="lvLos" title="Esc">Scène loslaten</button></div><div id="lvScenes"></div></div>
        <div class="blok"><h2>Cuelijsten</h2><div id="lvCues"></div></div>
      </div>
      <div class="stapel">
        <div class="blok"><h2>Vasthouden</h2>
          <div class="houders"><button class="houd strobe">STROBE</button><button class="houd smoke">SMOKE</button><button class="houd blinder">BLINDER</button></div>
          <p class="hint">Werkt zolang je vasthoudt. Toetsen: <code>S</code> strobe, <code>R</code> rook, <code>W</code> blinder.</p></div>
        <div class="blok"><h2>Snel</h2><div id="lvSnel"></div></div>
        <div class="blok"><h2>Laser &amp; looks</h2><div id="lvLooks"></div></div>
        <div class="blok"><h2>Faders</h2><div class="faders" id="lvFaders"></div></div>
      </div></div>`;
    podium = new Podium($('#lvPodium'), { modus: 'kijk', hoogte: 'min(40vh, 420px)' });
    houdKnop($('.houd.strobe'), 'strobe'); houdKnop($('.houd.smoke'), 'smoke'); houdKnop($('.houd.blinder'), 'blinder');
    houdAf = op('houd', soorten => ['strobe', 'smoke', 'blinder'].forEach(s => {
      const b = document.querySelector(`.houd.${s}`); if (b) b.classList.toggle('aan', soorten.has(s));
    }));
    $('#lvLos').onclick = () => doe('/api/scene', { actie: 'loslaten' });
    delen();

    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.scene !== undefined) return doe('/api/scene', { actie: 'laden', naam: b.dataset.scene });
      if (b.dataset.cue !== undefined) return doe('/api/actie', { soort: 'cue', arg: b.dataset.cue });
      if (b.dataset.cueactie) return doe('/api/cue', { actie: b.dataset.cueactie });
      if (b.dataset.actie) return doe('/api/actie', { soort: b.dataset.actie });
      if (b.dataset.tempo) return doe('/api/actie', { soort: 'tempo', arg: Number(b.dataset.tempo) });
      if (b.dataset.int) return doe('/api/show', { intensiteit: { modus: b.dataset.int } });
      if (b.dataset.snelkleur) return doe('/api/show', { kleur: { modus: 'vast', palet: [b.dataset.snelkleur] }, auto: { aan: false } });
      if (b.dataset.regenboog !== undefined) return doe('/api/show', { kleur: { modus: 'regenboog' } });
      if (b.dataset.lookmodus) return doe('/api/show', { looks: { modus: b.dataset.lookmodus } });
      if (b.dataset.look !== undefined) return doe('/api/show', { looks: { modus: 'vast', keuze: { [b.dataset.look]: Number(b.dataset.idx) } } });
    };
    el.oninput = e => {
      const i = e.target; if (!i.dataset.fader) return;
      const w = Number(i.value);
      i.parentElement.querySelector('b').textContent = w;
      if (i.dataset.fader === 'master') K.S.show.master = w;
      else if (i.dataset.fader === 'groep') K.S.show.groepen[i.dataset.id] = w;
      else { const f = K.S.faders.find(x => String(x.id) === i.dataset.id); if (f) f.waarde = w; }
      stuurFader(i.dataset.fader, i.dataset.id, w);
    };
  },
  state() { if ($('#lvScenes')) delen(); if (podium) podium.teken(); },
  live: liveBijwerken,
  weg() { if (podium) podium.weg(); podium = null; if (houdAf) houdAf(); houdAf = null; },
};
