// Programmer: lampen kiezen en met de hand instellen (gaat vóór de effecten). Daarna opslaan als scène.
import { K, api, doe, esc, $, $$, afremmen, clamp, dialoog, toast } from '../kern.js';
import { Podium } from '../podium.js';

const KLEUREN = [['#ff0000', 'Rood'], ['#ff5500', 'Oranje'], ['#ffcc00', 'Geel'], ['#00ff00', 'Groen'], ['#00ffff', 'Cyaan'],
  ['#0000ff', 'Blauw'], ['#7700ff', 'Paars'], ['#ff00ff', 'Roze'], ['#ffffff', 'Wit'], ['#ffd8a0', 'Warm wit']];
const AUTO = new Set(['dimmer', 'dimmer_fine', 'red', 'green', 'blue', 'white', 'amber', 'uv', 'cyan', 'magenta', 'yellow',
  'pan', 'pan_fine', 'tilt', 'tilt_fine']);
const gekozen = new Set();
let podium = null, alleKanalen = false;

const stuur = afremmen(waarden => {
  if (!gekozen.size) return;
  api('/api/programmer', { fixtures: [...gekozen], waarden }).catch(e => toast(e.message, true));
}, 50);

function lokaal(waarden) {
  // meteen in onze kopie zetten, dan springt het scherm niet terug
  for (const id of gekozen) {
    const p = K.S.programmer[id] ||= {};
    for (const [k, v] of Object.entries(waarden)) {
      if (k === 'kanalen') {
        p.kanalen ||= {};
        for (const [c, w] of Object.entries(v)) { if (w === null) delete p.kanalen[c]; else p.kanalen[c] = w; }
      } else if (v === null) delete p[k]; else p[k] = v;
    }
  }
}
function zet(waarden) { lokaal(waarden); stuur(waarden); }

function eerste() { const id = [...gekozen][0]; return id === undefined ? null : K.S.fixtures.find(f => f.id === id); }
function waardeVan(sleutel) { const f = eerste(); const p = f && K.S.programmer[f.id]; return p ? p[sleutel] : undefined; }

function lijst() {
  const S = K.S;
  const groepen = [...new Set(S.fixtures.map(f => f.groep))];
  const vb = Object.fromEntries((K.L.v || []).map(v => [v.id, v]));
  $('#prLijst').innerHTML = `
    <div class="rij" style="margin-top:0">
      <button data-kies="alles">Alles</button><button data-kies="geen">Geen</button><button data-kies="omkeren">Omkeren</button>
      <button data-kies="even">Even</button><button data-kies="oneven">Oneven</button>
      ${groepen.map(g => `<button data-groep="${esc(g)}">${esc(g)}</button>`).join('')}
    </div>
    <div class="fxlijst">${[...S.fixtures].sort((a, b) => a.x - b.x || a.id - b.id).map(f => `<button data-fx="${f.id}"
      class="${gekozen.has(f.id) ? 'aan' : ''} ${S.programmer[f.id] ? 'geprogd' : ''}"><i style="background:${vb[f.id] ? vb[f.id].c[0] : '#333'}"></i>${esc(f.naam)}</button>`).join('')}</div>`;
}

function bediening() {
  const el = $('#prBediening'); if (!el) return;
  const S = K.S;
  const fx = S.fixtures.filter(f => gekozen.has(f.id));
  if (!fx.length) {
    el.innerHTML = `<div class="blok"><h2>Bediening</h2><div class="leeg">Kies één of meer lampen: klik op het podium of in de lijst.<br>
      Wat je hier instelt gaat vóór de effecten, tot je het wist.</div></div>`;
    return;
  }
  const profielen = [...new Set(fx.map(f => f.profiel))];
  const functies = new Set(fx.flatMap(f => (S.profielen[f.profiel]?.kanalen || []).map(k => k.functie)));
  const heeftBeweging = functies.has('pan') || functies.has('tilt');
  const dim = waardeVan('dim'), kleur = waardeVan('kleur'), pan = waardeVan('pan'), tilt = waardeVan('tilt');
  const prof = profielen.length === 1 ? S.profielen[profielen[0]] : null;
  const f0 = eerste();
  const rawNu = (f0 && S.programmer[f0.id] && S.programmer[f0.id].kanalen) || {};
  const kanalen = prof ? prof.kanalen.map((k, i) => ({ k, i })).filter(({ k }) => alleKanalen || !AUTO.has(k.functie)) : [];

  el.innerHTML = `
    <div class="blok"><h2>${fx.length === 1 ? esc(fx[0].naam) : fx.length + ' lampen'}</h2>
      <div class="rij"><label>Dimmer</label><input type="range" min="0" max="100" value="${dim ?? 100}" id="prDim">
        <span class="waarde" id="prDimW">${dim ?? '–'}</span><button class="stil loslaten" data-los="dim" title="Loslaten: weer het effect volgen">×</button></div>
      <div class="knoppen" style="grid-template-columns:repeat(5,1fr)">
        ${[0, 25, 50, 75, 100].map(v => `<button data-dim="${v}" class="${dim === v ? 'aan' : ''}">${v}%</button>`).join('')}</div>
      <h3>Kleur ${kleur ? `<code>${kleur}</code>` : '<span class="hint">(volgt het effect)</span>'}
        <button class="stil loslaten" data-los="kleur">×</button></h3>
      <div class="swatches">${KLEUREN.map(([c, n]) => `<button class="swatch ${kleur === c ? 'aan' : ''}" style="background:${c}" title="${n}" data-kleur="${c}"></button>`).join('')}
        <input type="color" id="prKleur" value="${kleur || '#ffffff'}" title="Eigen kleur"></div>
      ${heeftBeweging ? `<h3>Positie ${pan !== undefined ? `<code>pan ${Math.round(pan)} · tilt ${Math.round(tilt ?? 50)}</code>` : '<span class="hint">(volgt het effect)</span>'}
        <button class="stil loslaten" data-los="pos">×</button></h3>
        <div class="xy" id="prXY"><i style="left:${pan ?? 50}%;top:${tilt ?? 50}%"></i></div>
        <div class="knoppen" style="grid-template-columns:repeat(4,1fr);margin-top:8px">
          <button data-pos="50,50">Midden</button><button data-pos="50,85">Publiek</button><button data-pos="50,10">Plafond</button><button data-pos="random">Verspreid</button></div>` : ''}
    </div>
    <div class="blok"><div class="paginakop" style="margin:0 0 6px"><h2 style="margin:0">Kanalen</h2><span class="vul"></span>
        <label class="hint"><input type="checkbox" id="prAlle" ${alleKanalen ? 'checked' : ''}> alle kanalen</label></div>
      ${!prof ? '<p class="hint">Losse kanalen kun je instellen als alle gekozen lampen hetzelfde profiel hebben.</p>'
        : !kanalen.length ? '<p class="hint">Dit profiel heeft geen extra kanalen (gobo, kleurwiel, …).</p>'
        : kanalen.map(({ k, i }) => {
          const nr = String(i + 1), v = rawNu[nr];
          return `<div class="kanaalrij ${v !== undefined ? 'gezet' : ''}" data-rij="${nr}">
            <span class="naam" title="${esc(k.naam)}">${nr}. ${esc(k.naam)}</span>
            <input type="range" min="0" max="255" value="${v ?? k.standaard ?? 0}" data-kanaal="${nr}">
            <input type="number" min="0" max="255" value="${v ?? ''}" placeholder="${k.standaard ?? 0}" data-kanaalnr="${nr}">
            <button class="stil loslaten" data-loskanaal="${nr}">×</button>
            ${k.opties && k.opties.length ? `<span></span><select data-optie="${nr}"><option value="">– kies –</option>
              ${k.opties.map(o => `<option value="${o.van}" ${v !== undefined && v >= o.van && v <= o.tot ? 'selected' : ''}>${o.van}–${o.tot}: ${esc(o.naam)}</option>`).join('')}</select>` : ''}
          </div>`; }).join('')}
    </div>`;
  const xy = $('#prXY');
  if (xy) {
    const zetXY = e => {
      const b = xy.getBoundingClientRect();
      const p = clamp((e.clientX - b.left) / b.width * 100, 0, 100), t = clamp((e.clientY - b.top) / b.height * 100, 0, 100);
      xy.querySelector('i').style.left = p + '%'; xy.querySelector('i').style.top = t + '%';
      zet({ pan: Math.round(p * 10) / 10, tilt: Math.round(t * 10) / 10 });
    };
    xy.onpointerdown = e => { K.bezig = true; xy.setPointerCapture(e.pointerId); zetXY(e); xy.onpointermove = zetXY; };
    xy.onpointerup = xy.onpointercancel = () => { xy.onpointermove = null; };
  }
}

function selectieGewijzigd() { lijst(); bediening(); if (podium) podium.teken(); }

async function opslaan() {
  const S = K.S;
  if (!Object.keys(S.programmer).length) return toast('De programmer is leeg: stel eerst lampen in', true);
  dialoog({
    titel: 'Opslaan als scène',
    html: `<div class="velden">
      <label>Naam<input id="scNaam" placeholder="bijv. Rood-wit intro"></label>
      <label>Overvloeien (seconden)<input id="scFade" type="number" min="0" max="60" step="0.1" value="${S.show.fade}"></label>
      <label>Kleur van de knop<input id="scKleur" type="color" value="#ffc400"></label>
      <label class="check"><input type="checkbox" id="scEff"> ook de huidige effecten bewaren</label>
      <label class="check"><input type="checkbox" id="scAlleen" ${gekozen.size ? '' : 'disabled'}> alleen de gekozen lampen</label>
    </div><p class="hint">Een scène met vaste waarden overschrijft bij het laden alleen die lampen; de rest blijft de effecten volgen.</p>`,
    knoppen: [{ tekst: 'Annuleren' }, { tekst: 'Opslaan', klasse: 'primair', actie: async d => {
      const naam = $('#scNaam', d.el).value.trim();
      if (!naam) { toast('Geef de scène een naam', true); return false; }
      const r = await doe('/api/scene', { actie: 'opslaan', naam, inhoud: $('#scEff', d.el).checked ? 'beide' : 'vast',
        fixtures: $('#scAlleen', d.el).checked ? [...gekozen] : null, fade: Number($('#scFade', d.el).value), kleur: $('#scKleur', d.el).value },
        'Scène opgeslagen: ' + naam);
      return r !== null;
    } }],
  });
}

export default {
  id: 'programmer', titel: 'Programmer',
  icoon: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',
  teken(el) {
    for (const id of [...gekozen]) if (!K.S.fixtures.some(f => f.id === id)) gekozen.delete(id);
    el.innerHTML = `<div class="paginakop"><h1>Programmer</h1><span class="hint">Kies lampen en stel ze met de hand in.</span><span class="vul"></span>
        <button id="prWisSel">Gekozen wissen</button><button id="prWis" class="gevaar">Alles wissen</button>
        <button id="prOpslaan" class="primair">Opslaan als scène…</button></div>
      <div class="prog"><div class="stapel"><div id="prPodium"></div><div class="blok"><h2>Lampen</h2><div id="prLijst"></div></div></div>
        <div class="stapel" id="prBediening"></div></div>`;
    podium = new Podium($('#prPodium'), { modus: 'kies', hoogte: 'min(46vh, 480px)', geselecteerd: gekozen,
      bijSelectie: () => { lijst(); bediening(); } });
    lijst(); bediening();
    $('#prWisSel').onclick = () => gekozen.size && doe('/api/programmer', { actie: 'wissen', fixtures: [...gekozen] });
    $('#prWis').onclick = () => doe('/api/programmer', { actie: 'wissen' });
    $('#prOpslaan').onclick = opslaan;

    el.onclick = e => {
      const b = e.target.closest('button'); if (!b) return;
      const S = K.S;
      if (b.dataset.fx) {
        const id = Number(b.dataset.fx);      // in de lijst werkt elke lamp als aan/uit-knop
        gekozen.has(id) ? gekozen.delete(id) : gekozen.add(id);
        return selectieGewijzigd();
      }
      if (b.dataset.kies) {
        const ids = [...S.fixtures].sort((a, c) => a.x - c.x || a.id - c.id).map(f => f.id);
        const k = b.dataset.kies;
        const nieuw = k === 'alles' ? ids : k === 'geen' ? [] : k === 'omkeren' ? ids.filter(i => !gekozen.has(i))
          : ids.filter((_, i) => (i % 2 === 0) === (k === 'oneven'));
        gekozen.clear(); nieuw.forEach(i => gekozen.add(i));
        return selectieGewijzigd();
      }
      if (b.dataset.groep !== undefined) {
        gekozen.clear(); S.fixtures.filter(f => f.groep === b.dataset.groep).forEach(f => gekozen.add(f.id));
        return selectieGewijzigd();
      }
      if (b.dataset.dim !== undefined) { zet({ dim: Number(b.dataset.dim) }); return bediening(); }
      if (b.dataset.kleur) { zet({ kleur: b.dataset.kleur }); return bediening(); }
      if (b.dataset.pos) {
        if (b.dataset.pos === 'random') {
          [...gekozen].forEach((id, i) => api('/api/programmer', { fixtures: [id], waarden: { pan: 15 + (i * 37) % 70, tilt: 30 + (i * 23) % 40 } }));
          [...gekozen].forEach((id, i) => { const p = S.programmer[id] ||= {}; p.pan = 15 + (i * 37) % 70; p.tilt = 30 + (i * 23) % 40; });
        } else { const [p, t] = b.dataset.pos.split(',').map(Number); zet({ pan: p, tilt: t }); }
        return bediening();
      }
      if (b.dataset.los) {
        zet(b.dataset.los === 'pos' ? { pan: null, tilt: null } : { [b.dataset.los]: null });
        return bediening();
      }
      if (b.dataset.loskanaal) { zet({ kanalen: { [b.dataset.loskanaal]: null } }); return bediening(); }
    };
    el.oninput = e => {
      const i = e.target;
      if (i.id === 'prDim') { $('#prDimW').textContent = i.value; zet({ dim: Number(i.value) }); }
      else if (i.id === 'prKleur') zet({ kleur: i.value });
      else if (i.dataset.kanaal || i.dataset.kanaalnr) {
        const nr = i.dataset.kanaal || i.dataset.kanaalnr, v = clamp(Number(i.value) || 0, 0, 255);
        const rij = i.closest('.kanaalrij');
        if (i.dataset.kanaal) rij.querySelector('[data-kanaalnr]').value = v; else rij.querySelector('[data-kanaal]').value = v;
        rij.classList.add('gezet');
        zet({ kanalen: { [nr]: v } });
      }
    };
    el.onchange = e => {
      const i = e.target;
      if (i.id === 'prAlle') { alleKanalen = i.checked; bediening(); }
      else if (i.dataset.optie && i.value !== '') { zet({ kanalen: { [i.dataset.optie]: Number(i.value) } }); bediening(); }
      else if (i.id === 'prKleur') bediening();
    };
  },
  state() { if ($('#prLijst')) { lijst(); if (!K.bezig) bediening(); } if (podium) podium.teken(); },
  live(L) {
    if (podium) podium.teken();
    const vb = Object.fromEntries((L.v || []).map(v => [v.id, v]));
    $$('#prLijst [data-fx] i').forEach(i => { const v = vb[i.parentElement.dataset.fx]; if (v) i.style.background = v.c[0]; });
  },
  weg() { if (podium) podium.weg(); podium = null; },
};
