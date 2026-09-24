// Effecten: kleur, intensiteit en beweging op de beat, looks (laser), auto-show en energie.
import { K, api, doe, esc, $, afremmen, zetShow, toast, invoer } from '../kern.js';

const SNELHEDEN = [[0.25, '¼ beat'], [0.5, '½ beat'], [1, '1 beat'], [2, '2 beats'], [4, '4 beats'], [8, '8 beats'], [16, '16 beats']];
const RONDES = [[1, '1 beat'], [2, '2 beats'], [4, '4 beats'], [8, '8 beats'], [16, '16 beats'], [32, '32 beats']];
const KLEUREN = [['#ff0000', 'rood'], ['#ff6600', 'oranje'], ['#ffcc00', 'geel'], ['#00ff00', 'groen'], ['#00ffff', 'cyaan'],
  ['#0000ff', 'blauw'], ['#8800ff', 'paars'], ['#ff00ff', 'roze'], ['#ffffff', 'wit']];

const modusKnoppen = (p, modi, huidig) =>
  `<div class="knoppen">${modi.map(([v, t]) => `<button data-set="${p}" data-val='${JSON.stringify(v)}' class="${v === huidig ? 'aan' : ''}">${esc(t)}</button>`).join('')}</div>`;
const keuzelijst = (p, opties, huidig) =>
  `<select data-set="${p}" data-num="1">${opties.map(([v, t]) => `<option value="${v}" ${Number(v) === Number(huidig) ? 'selected' : ''}>${t}</option>`).join('')}</select>`;
const schuif = (p, label, waarde, min = 0, max = 100) =>
  `<div class="rij"><label>${label}</label><input type="range" min="${min}" max="${max}" value="${waarde}" data-set="${p}"><span class="waarde">${waarde}</span></div>`;

const stuurSchuif = afremmen((p, v) => zetShow(p, v, false), 80);

function teken(el) {
  const S = K.S, s = S.show, M = S.modi;
  const palet = s.kleur.palet || [];
  const eigen = palet.filter(c => !KLEUREN.some(([k]) => k === c));
  const lookProfielen = Object.entries(S.profielen).filter(([pid, p]) => p.looks && p.looks.length && S.fixtures.some(f => f.profiel === pid));
  el.innerHTML = `
  <div class="paginakop"><h1>Effecten</h1><span class="hint">Alles loopt op de beat. Een scène bewaart deze instellingen.</span><span class="vul"></span>
    <button id="efScene" class="primair">Opslaan als scène…</button></div>
  <div class="raster">
    <div class="blok">
      <h2>Kleur</h2>
      ${modusKnoppen('kleur.modus', M.kleur, s.kleur.modus)}
      <h3>Palet (volgorde = nummer)</h3>
      <div class="swatches">
        ${KLEUREN.concat(eigen.map(c => [c, 'eigen'])).map(([c, n]) => { const i = palet.indexOf(c);
          return `<button class="swatch ${i >= 0 ? 'aan' : ''}" style="background:${c}" title="${n}" data-palet="${c}">${i >= 0 ? `<span>${i + 1}</span>` : ''}</button>`; }).join('')}
        <label class="swatch" style="background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red)" title="eigen kleur">
          <input type="color" id="eigenKleur" style="opacity:0;width:100%;height:100%;cursor:pointer"></label>
      </div>
      <div class="rij"><label>Snelheid</label>${keuzelijst('kleur.snelheid', SNELHEDEN, s.kleur.snelheid)}</div>
      ${schuif('kleur.spreiding', 'Spreiding', s.kleur.spreiding)}
    </div>

    <div class="blok">
      <h2>Intensiteit</h2>
      ${modusKnoppen('intensiteit.modus', M.intensiteit, s.intensiteit.modus)}
      <div class="rij"><label>Snelheid</label>${keuzelijst('intensiteit.snelheid', SNELHEDEN, s.intensiteit.snelheid)}</div>
    </div>

    <div class="blok">
      <h2>Beweging (moving heads)</h2>
      ${modusKnoppen('beweging.modus', M.beweging, s.beweging.modus)}
      <div class="rij"><label>Eén ronde duurt</label>${keuzelijst('beweging.snelheid', RONDES, s.beweging.snelheid)}</div>
      ${schuif('beweging.grootte', 'Grootte', s.beweging.grootte)}
      ${schuif('beweging.spreiding', 'Spreiding', s.beweging.spreiding)}
      ${schuif('beweging.pan', 'Midden pan', s.beweging.pan)}
      ${schuif('beweging.tilt', 'Midden tilt', s.beweging.tilt)}
    </div>

    <div class="blok">
      <h2>Algemeen</h2>
      <div class="rij"><button data-bpm="-1">−</button><b style="font-size:30px;min-width:96px;text-align:center" class="nr">${s.bpm}</b>
        <button data-bpm="1">+</button><button class="primair" id="efTap" style="flex:1;font-size:18px;padding:12px">TAP</button></div>
      <div class="knoppen twee">
        <button data-set="beat.auto" data-val="true" class="${s.beat.auto ? 'aan' : ''}">♪ BPM AUTOMATISCH</button>
        <button data-set="beat.auto" data-val="false" class="${!s.beat.auto ? 'aan' : ''}">BPM HANDMATIG</button></div>
      <div class="rij"><label>Tempo-factor</label>${keuzelijst('tempo_factor', [[0.25, '¼× (heel rustig)'], [0.5, '½×'], [1, '1× (normaal)'], [2, '2×'], [4, '4× (druk)']], s.tempo_factor)}</div>
      ${schuif('master', 'Master', s.master)}
      ${schuif('strobe_hz', 'Strobe (Hz)', s.strobe_hz, 2, 25)}
      <div class="rij"><label>Scène-fade (s)</label><input type="number" min="0" max="60" step="0.1" value="${s.fade}" data-set="fade" data-num="1"></div>
      <h3>Auto-show</h3>
      <div class="knoppen twee">
        <button data-set="auto.aan" data-val="${!s.auto.aan}" class="${s.auto.aan ? 'aan' : ''}">AUTO-SHOW${s.auto.aan ? ' (AAN)' : ''}</button>
        ${keuzelijst('auto.elke', [[8, 'wissel elke 8 beats'], [16, 'elke 16 beats'], [32, 'elke 32 beats'], [64, 'elke 64 beats']], s.auto.elke)}
      </div>
      <p class="hint">Auto-show kiest zelf steeds nieuwe kleuren, effecten en bewegingen.</p>
      <h3>Energie van de muziek</h3>
      <div class="knoppen twee">
        <button data-set="energie.aan" data-val="${!s.energie.aan}" class="${s.energie.aan ? 'aan' : ''}">SHOW VOLGT ENERGIE${s.energie.aan ? ' (AAN)' : ''}</button>
        <button data-set="energie.flits_bij_drop" data-val="${!s.energie.flits_bij_drop}" class="${s.energie.flits_bij_drop ? 'aan' : ''}">FLITS BIJ DROP${s.energie.flits_bij_drop ? ' (AAN)' : ''}</button>
      </div>
      <div class="meter" style="margin-top:10px"><i id="efMeter"></i></div><p class="hint" id="efEnergie">–</p>
      <p class="hint">Rustig = langzame, kleine bewegingen en wat gedimd. Extreem = snel, groot en vol. Een drop geeft een korte witte flits.</p>
    </div>

    <div class="blok">
      <h2>Looks (laser e.d.)</h2>
      ${modusKnoppen('looks.modus', [['uit', 'Uit'], ['vast', 'Vaste look'], ['wissel', 'Automatisch wisselen']], s.looks.modus)}
      <div class="rij"><label>Wissel elke</label>${keuzelijst('looks.elke', [[4, '4 beats'], [8, '8 beats'], [16, '16 beats'], [32, '32 beats']], s.looks.elke)}</div>
      ${lookProfielen.length ? lookProfielen.map(([pid, p]) => `<h3>${esc(p.naam)}</h3><div class="knoppen">
          ${p.looks.map((l, i) => `<button data-look="${esc(pid)}" data-idx="${i}" class="${s.looks.modus === 'vast' && (s.looks.keuze[pid] || 0) === i ? 'aan' : ''}">${esc(l.naam)}</button>`).join('')}</div>`).join('')
        : '<p class="hint">Geen lampen met looks. Looks maak je in het tabblad Profielen.</p>'}
    </div>
  </div>`;
  $('#eigenKleur').addEventListener('change', e => zetShow('kleur.palet', (s.kleur.palet || []).concat([e.target.value]).slice(-8)));
  energie(K.L);
}

function energie(L) {
  const st = L && L.s; if (!st) return;
  const bron = Object.values(st.luister || {}).find(i => i.energie !== null && i.energie !== undefined);
  const m = $('#efMeter'), t = $('#efEnergie'); if (!m) return;
  const e = bron ? bron.energie : null;
  m.style.width = e === null ? '0%' : Math.round(e * 100) + '%';
  t.textContent = e === null ? 'Hoort nu geen muziek' :
    `Energie ${Math.round(e * 100)}% · ${e < 0.3 ? 'rustig' : e < 0.6 ? 'normaal' : e < 0.8 ? 'druk' : 'EXTREEM'}` + (bron.drop ? ' · 💥 DROP!' : '');
}

export default {
  id: 'effecten', titel: 'Effecten',
  icoon: '<path d="M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2z"/><path d="M19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7z"/>',
  teken(el) {
    teken(el);
    el.onclick = async e => {
      const b = e.target.closest('button, .swatch'); if (!b) return;
      if (b.dataset.set !== undefined && b.dataset.val !== undefined) {
        let v = b.dataset.val; try { v = JSON.parse(v); } catch (x) { /* tekst */ }
        return zetShow(b.dataset.set, v);
      }
      if (b.id === 'efTap') return doe('/api/tap', {});
      if (b.id === 'efScene') {
        const naam = await invoer('Huidige effecten opslaan als scène', '', 'Kleur, intensiteit, beweging en looks worden bewaard.');
        if (naam) doe('/api/scene', { actie: 'opslaan', naam, inhoud: 'effecten' }, 'Scène opgeslagen');
        return;
      }
      if (b.dataset.bpm) return zetShow('bpm', Math.round(K.S.show.bpm) + Number(b.dataset.bpm));
      if (b.dataset.palet) {
        const c = b.dataset.palet; let p = [...(K.S.show.kleur.palet || [])];
        p = p.includes(c) ? p.filter(x => x !== c) : p.concat([c]);
        if (!p.length) return toast('Minimaal één kleur nodig', true);
        return zetShow('kleur.palet', p);
      }
      if (b.dataset.look !== undefined) {
        await doe('/api/show', { looks: { modus: 'vast', keuze: { [b.dataset.look]: Number(b.dataset.idx) } } });
      }
    };
    el.oninput = e => {
      const i = e.target;
      if (i.type === 'range' && i.dataset.set) {
        const w = i.nextElementSibling; if (w) w.textContent = i.value;
        stuurSchuif(i.dataset.set, Number(i.value));
      }
    };
    el.onchange = e => {
      const i = e.target;
      if ((i.tagName === 'SELECT' || i.type === 'number') && i.dataset.set) zetShow(i.dataset.set, i.dataset.num ? Number(i.value) : i.value);
      else if (i.type === 'range' && i.dataset.set) zetShow(i.dataset.set, Number(i.value));
    };
  },
  live: energie,
};
