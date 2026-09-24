// Monitor: alle 512 kanalen van een universe, live. Handig om te zien wat er echt naar de lampen gaat.
import { K, esc, $, zetMonitor } from '../kern.js';

let universe = 1, cellen = [];

function teken(el) {
  const S = K.S;
  const universes = [...new Set([1, ...S.fixtures.map(f => f.universe), ...S.uitgangen.map(u => u.universe)])].sort((a, b) => a - b);
  if (!universes.includes(universe)) universe = universes[0];
  const bezet = {};
  for (const f of S.fixtures.filter(x => x.universe === universe)) {
    const p = S.profielen[f.profiel]; if (!p) continue;
    p.kanalen.forEach((k, i) => { bezet[f.adres + i] = { f, k, i }; });
  }
  el.innerHTML = `<div class="paginakop"><h1>DMX-monitor</h1><span class="hint">Wat er nu echt naar buiten gaat.</span><span class="vul"></span>
      <label class="hint">Universe <select id="moU">${universes.map(u => `<option ${u === universe ? 'selected' : ''}>${u}</option>`).join('')}</select></label></div>
    <div class="blok"><div class="dmxraster" id="moRaster">${Array.from({ length: 512 }, (_, n) => {
      const b = bezet[n + 1];
      return `<div class="${b ? 'bezet' : ''} ${b && b.i === 0 ? 'start' : ''}" title="${n + 1}${b ? ` · ${esc(b.f.naam)} · ${b.i + 1}: ${esc(b.k.naam)}` : ''}">
        <i></i><b>${n + 1}</b><span></span></div>`; }).join('')}</div>
    <p class="hint">Blauw = kanaal van een lamp (lichtblauwe streep = eerste kanaal). Beweeg over een vakje voor de naam.</p></div>`;
  cellen = [...$('#moRaster').children].map(d => [d.querySelector('i'), d.querySelector('span')]);
  $('#moU').onchange = e => { universe = Number(e.target.value); zetMonitor(universe); teken(el); };
  zetMonitor(universe);
}

export default {
  id: 'monitor', titel: 'Monitor',
  icoon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  teken,
  state(el) { if ($('#moRaster')) teken(el); },
  live(L) {
    if (!L.f || !cellen.length) return;
    for (let n = 0; n < 512; n++) {
      const v = L.f[n];
      const [i, s] = cellen[n];
      if (s._v === v) continue;
      s._v = v; s.textContent = v || '';
      i.style.height = (v / 255 * 100) + '%';
    }
  },
  weg() { cellen = []; zetMonitor(0); },
};
