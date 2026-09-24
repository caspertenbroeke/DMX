// Podium: plattegrond met live licht. Sleep lampen naar hun echte plek (links/rechts bepaalt de volgorde van effecten).
import { K, api, esc, $, toast, clamp } from '../kern.js';
import { Podium } from '../podium.js';

let podium = null;
const gekozen = new Set();

async function bewaar() {
  try { await api('/api/fixtures', K.S.fixtures); }
  catch (e) { toast(e.message, true); }
}

function paneel() {
  const el = $('#pdPaneel'); if (!el) return;
  const fx = K.S.fixtures.filter(f => gekozen.has(f.id));
  if (!fx.length) {
    el.innerHTML = '<p class="hint">Klik op een lamp om hem te bewerken. Sleep om te verplaatsen. Shift+klik of een rechthoek slepen kiest er meer.</p>';
    return;
  }
  if (fx.length === 1) {
    const f = fx[0], p = K.S.profielen[f.profiel];
    el.innerHTML = `<div class="velden">
      <label>Naam<input data-pk="naam" value="${esc(f.naam)}"></label>
      <label>Links → rechts (0–100)<input type="number" min="0" max="100" step="0.5" data-pk="x" value="${f.x}"></label>
      <label>Achter → voor (0–100)<input type="number" min="0" max="100" step="0.5" data-pk="y" value="${f.y}"></label>
      ${p && p.soort === 'bar' ? `<label>Breedte (0–100)<input type="number" min="1" max="100" data-pk="breedte" value="${f.breedte}"></label>` : ''}
    </div><p class="hint">${esc(p ? p.naam : '')} · universe ${f.universe}, adres ${f.adres}</p>`;
    return;
  }
  el.innerHTML = `<p><b>${fx.length} lampen gekozen</b></p><div class="rij">
    <button data-uitlijn="rij">Op een rij (gelijk verdeeld)</button><button data-uitlijn="y">Zelfde hoogte</button>
    <button data-uitlijn="spiegel">Spiegelen</button></div>`;
}

export default {
  id: 'podium', titel: 'Podium',
  icoon: '<rect x="2" y="14" width="20" height="6" rx="1"/><path d="M6 14l2-8M18 14l-2-8M12 14V4"/><circle cx="8" cy="5" r="1"/><circle cx="16" cy="5" r="1"/>',
  teken(el) {
    el.innerHTML = `<div class="paginakop"><h1>Podium</h1><span class="hint">Zet je lampen op hun plek. De volgorde van links naar rechts
      bepaalt hoe chases en golven lopen.</span><span class="vul"></span>
      <label class="hint"><input type="checkbox" id="pdLabels" checked> namen</label></div>
      <div id="pdPodium"></div><div class="blok" style="margin-top:14px"><h2>Gekozen</h2><div id="pdPaneel"></div></div>`;
    podium = new Podium($('#pdPodium'), { modus: 'verplaats', hoogte: 'calc(100vh - 290px)', geselecteerd: gekozen,
      bijVerplaats: () => { paneel(); bewaar(); }, bijSelectie: paneel });
    $('#pdPodium').style.minHeight = '360px';
    paneel();
    $('#pdLabels').onchange = e => { podium.o.labels = e.target.checked; podium.teken(); };
    el.onchange = e => {
      const i = e.target; if (!i.dataset.pk) return;
      const f = K.S.fixtures.find(x => gekozen.has(x.id)); if (!f) return;
      f[i.dataset.pk] = i.dataset.pk === 'naam' ? i.value : clamp(Number(i.value) || 0, 0, 100);
      podium.teken(); bewaar();
    };
    el.onclick = e => {
      const b = e.target.closest('[data-uitlijn]'); if (!b) return;
      const fx = K.S.fixtures.filter(f => gekozen.has(f.id)).sort((a, c) => a.x - c.x);
      if (b.dataset.uitlijn === 'rij') {
        const a = fx[0].x, z = fx.at(-1).x > a ? fx.at(-1).x : a + 60;
        fx.forEach((f, i) => { f.x = Math.round((a + (z - a) * i / Math.max(1, fx.length - 1)) * 2) / 2; });
      } else if (b.dataset.uitlijn === 'y') {
        const y = fx.reduce((s, f) => s + f.y, 0) / fx.length; fx.forEach(f => { f.y = Math.round(y * 2) / 2; });
      } else fx.forEach(f => { f.x = 100 - f.x; });
      podium.teken(); paneel(); bewaar();
    };
  },
  state() { if (podium) { podium.teken(); if (!document.activeElement?.dataset?.pk) paneel(); } },
  live() { if (podium) podium.teken(); },
  weg() { if (podium) podium.weg(); podium = null; },
};
