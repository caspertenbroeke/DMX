// Profielen: wat elk kanaal van een lamp doet. Zelf maken, of inlezen uit QLC+ (.qxf) of de Open Fixture Library (.json).
import { K, api, doe, esc, $, kloon, dialoog, toast, vraag, laadState, kiesBestand, download } from '../kern.js';

let P = null, keuze = null, optiesOpen = null;
const vuil = () => P !== null && JSON.stringify(P) !== JSON.stringify(K.S.profielen);

function leesLook(tekst) {
  const w = {};
  tekst.split(/[,;\s]+/).filter(Boolean).forEach(deel => {
    const m = deel.match(/^(\d+)=(\d+)$/);
    if (m) w[m[1]] = Math.min(255, Number(m[2]));
  });
  return w;
}
function leesOpties(tekst) {
  return tekst.split('\n').map(r => r.match(/^\s*(\d+)\s*[-–]\s*(\d+)\s+(.*)$/)).filter(Boolean)
    .map(m => ({ van: Math.min(255, Number(m[1])), tot: Math.min(255, Number(m[2])), naam: m[3].trim() }));
}
function nieuwId(naam) {
  let basis = naam.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'profiel', id = basis, n = 2;
  while (P[id]) id = `${basis}_${n++}`;
  return id;
}

function teken() {
  const S = K.S;
  if (P === null) P = kloon(S.profielen);
  if (!P[keuze]) keuze = Object.keys(P).sort((a, b) => P[a].naam.localeCompare(P[b].naam))[0] || null;
  const p = P[keuze];
  const inGebruik = pid => S.fixtures.filter(f => f.profiel === pid).map(f => f.naam);
  const lookTekst = l => Object.entries(l.waarden).map(([c, v]) => `${c}=${v}`).join(', ');
  $('#pfInhoud').innerHTML = `
    <div class="rij" style="margin-top:0">
      <select id="pfKeuze" style="flex:1;min-width:220px">${Object.entries(P).sort((a, b) => a[1].naam.localeCompare(b[1].naam))
        .map(([id, q]) => `<option value="${esc(id)}" ${id === keuze ? 'selected' : ''}>${esc(q.naam)} (${q.kanalen.length} ch)${inGebruik(id).length ? ' ●' : ''}</option>`).join('')}</select>
      <button id="pfNieuw">+ Nieuw</button><button id="pfKopie" ${p ? '' : 'disabled'}>Kopie</button>
      <button id="pfExport" ${p ? '' : 'disabled'}>Exporteren</button><button class="gevaar" id="pfWeg" ${p ? '' : 'disabled'}>Verwijderen</button>
    </div>
    ${p ? `<div class="blok">
      <div class="velden">
        <label>Naam<input id="pfNaam" value="${esc(p.naam)}"></label>
        <label>Merk<input id="pfFabrikant" value="${esc(p.fabrikant || '')}"></label>
        <label>Soort<select id="pfSoort">${Object.entries(S.soorten).map(([k, v]) => `<option value="${k}" ${k === p.soort ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
      </div>
      <p class="hint">Gebruikt door: ${esc(inGebruik(keuze).join(', ') || 'geen lampen')}. Zet per kanaal wat het doet (zie de handleiding van de lamp).
        <b>Standaard</b> = waarde als niets anders het kanaal bestuurt (bijv. de shutter op 'open'). <b>Strobe</b>/<b>Rook</b> = waarde zolang die knop
        ingedrukt is (leeg = automatisch). <b>Cel</b> = segment of pixel bij LED-bars (0 = hele lamp).</p>
      <div class="scroll"><table>
        <tr><th style="width:36px">CH</th><th>Naam</th><th style="width:170px">Functie</th><th style="width:74px">Standaard</th><th style="width:74px">Strobe</th>
          <th style="width:74px">Rook</th><th style="width:60px">Cel</th><th style="width:70px">Opties</th><th style="width:76px"></th></tr>
        ${p.kanalen.map((k, i) => `<tr><td class="nr"><b>${i + 1}</b></td>
          <td><input data-ch="${i}" data-k="naam" value="${esc(k.naam)}"></td>
          <td><select data-ch="${i}" data-k="functie">${Object.entries(S.functies).map(([f, t]) => `<option value="${f}" ${f === k.functie ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></td>
          <td><input type="number" min="0" max="255" data-ch="${i}" data-k="standaard" value="${k.standaard ?? 0}"></td>
          <td><input type="number" min="0" max="255" data-ch="${i}" data-k="strobe" value="${k.strobe ?? ''}" placeholder="auto"></td>
          <td><input type="number" min="0" max="255" data-ch="${i}" data-k="rook" value="${k.rook ?? ''}" placeholder="auto"></td>
          <td><input type="number" min="0" max="128" data-ch="${i}" data-k="kop" value="${k.kop || 0}"></td>
          <td><button class="stil" data-opties="${i}">${k.opties && k.opties.length ? k.opties.length : '–'}</button></td>
          <td style="white-space:nowrap"><button class="stil icoon" data-chop="${i}">↑</button><button class="stil icoon" data-chweg="${i}">×</button></td></tr>
          ${optiesOpen === i ? `<tr><td></td><td colspan="8"><p class="hint">Eén per regel: <code>van-tot naam</code>, bijv. <code>10-19 Rood</code>. In de Programmer kies je dan uit deze lijst.</p>
            <textarea rows="6" data-optietekst="${i}">${esc((k.opties || []).map(o => `${o.van}-${o.tot} ${o.naam}`).join('\n'))}</textarea></td></tr>` : ''}`).join('')}
      </table></div>
      <div class="rij"><button id="chNieuw">+ Kanaal</button><button id="chCellen">Cellen maken…</button><span class="hint">${p.kanalen.length} kanalen</span></div>
      <h3>Looks</h3>
      <p class="hint">Een look zet een paar kanalen op een vaste waarde, bijvoorbeeld een laserpatroon: <code>19=208, 20=80</code>.
        In Effecten kies je een vaste look of laat je ze automatisch wisselen.</p>
      <table>${p.looks.map((l, i) => `<tr><td style="width:40%"><input data-look="${i}" data-k="naam" value="${esc(l.naam)}"></td>
        <td><input data-look="${i}" data-k="waarden" value="${esc(lookTekst(l))}"></td>
        <td style="width:40px"><button class="stil icoon" data-lookweg="${i}">×</button></td></tr>`).join('')}</table>
      <div class="rij"><button id="lookNieuw">+ Look</button></div>
    </div>` : '<div class="leeg">Geen profielen.</div>'}`;
  $('#pfOpslaan').disabled = !vuil();
}

async function importeren() {
  const b = await kiesBestand('.qxf,.json,.xml');
  if (!b) return;
  let res;
  try { res = await api('/api/profiel-import', { naam: b.naam, inhoud: b.inhoud }); }
  catch (e) { return toast(e.message, true); }
  const d = dialoog({
    titel: `Importeren: ${b.naam}`,
    html: `<p class="hint">Welke modi wil je toevoegen?</p>${res.profielen.map((m, i) => `<label class="rij" style="color:var(--tekst)">
      <input type="checkbox" data-imp="${i}" ${i === 0 ? 'checked' : ''}> ${esc(m.profiel.naam)} <span class="hint">(${m.profiel.kanalen.length} kanalen)</span></label>`).join('')}`,
    knoppen: [{ tekst: 'Annuleren' }, { tekst: 'Toevoegen', klasse: 'primair', actie: async d2 => {
      const gekozen = res.profielen.filter((_, i) => d2.el.querySelector(`[data-imp="${i}"]`).checked);
      for (const m of gekozen) { const id = nieuwId(m.profiel.naam); P[id] = m.profiel; keuze = id; }
      if (gekozen.length) await opslaan();
    } }],
  });
  return d;
}

async function opslaan() {
  try { await api('/api/profielen', P); await laadState(true); P = kloon(K.S.profielen); teken(); toast('Profielen opgeslagen'); }
  catch (e) { toast(e.message, true); }
}

function cellenMaken() {
  const p = P[keuze];
  dialoog({
    titel: 'Cellen maken (LED-bar / pixels)',
    html: `<p class="hint">Voegt kanalen toe voor een lamp met losse segmenten, bijvoorbeeld een LED-bar met 8 RGB-segmenten.
      De effecten lopen dan over de segmenten heen.</p><div class="velden">
      <label>Aantal cellen<input id="clAantal" type="number" min="1" max="128" value="8"></label>
      <label>Kanalen per cel<select id="clSoort"><option value="red,green,blue">R G B</option><option value="red,green,blue,white">R G B W</option>
        <option value="dimmer,red,green,blue">Dim R G B</option><option value="red,green,blue,white,amber,uv">R G B W A UV</option><option value="dimmer">Dimmer</option></select></label></div>`,
    knoppen: [{ tekst: 'Annuleren' }, { tekst: 'Toevoegen', klasse: 'primair', actie: d => {
      const n = Number($('#clAantal', d.el).value) || 1, soort = $('#clSoort', d.el).value.split(',');
      const namen = { red: 'Rood', green: 'Groen', blue: 'Blauw', white: 'Wit', amber: 'Amber', uv: 'UV', dimmer: 'Dimmer' };
      for (let c = 1; c <= n; c++) for (const f of soort) p.kanalen.push({ naam: `${namen[f]} ${c}`, functie: f, standaard: 0, strobe: null, rook: null, kop: c });
      if (p.soort === 'par') p.soort = 'bar';
      teken();
    } }],
  });
}

export default {
  id: 'profielen', titel: 'Profielen',
  icoon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8M8 9h2"/>',
  vuil,
  teken(el) {
    P = null;
    el.innerHTML = `<div class="paginakop"><h1>Profielen</h1><span class="hint">Wat elk kanaal van een lamp doet.</span><span class="vul"></span>
        <button id="pfImport">Importeren (.qxf / .json)…</button><button id="pfHerstel">Ongedaan maken</button>
        <button id="pfOpslaan" class="primair" disabled>Opslaan</button></div><div id="pfInhoud"></div>`;
    teken();
    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b || b.disabled) return;
      const p = P[keuze];
      if (b.id === 'pfImport') return importeren();
      if (b.id === 'pfOpslaan') return opslaan();
      if (b.id === 'pfHerstel') { P = null; return teken(); }
      if (b.id === 'pfNieuw') {
        const id = nieuwId('eigen profiel');
        P[id] = { naam: 'Nieuw profiel', fabrikant: '', soort: 'par', bron: 'eigen', looks: [],
          kanalen: [{ naam: 'Dimmer', functie: 'dimmer', standaard: 0, strobe: null, rook: null, kop: 0 }] };
        keuze = id; return teken();
      }
      if (b.id === 'pfKopie') { const id = nieuwId(p.naam + ' kopie'); P[id] = kloon(p); P[id].naam = p.naam + ' (kopie)'; keuze = id; return teken(); }
      if (b.id === 'pfExport') return download(`${p.naam.replace(/[^\w\- ]+/g, '_')}.dmxprofiel.json`, JSON.stringify(p, null, 2));
      if (b.id === 'pfWeg') {
        const gebruik = K.S.fixtures.filter(f => f.profiel === keuze).map(f => f.naam);
        if (gebruik.length) return toast('Dit profiel is nog in gebruik door: ' + gebruik.join(', '), true);
        if (await vraag(`Profiel "${p.naam}" verwijderen?`, 'Verwijderen', true)) { delete P[keuze]; keuze = null; teken(); }
        return;
      }
      if (b.id === 'chNieuw') { p.kanalen.push({ naam: 'Kanaal ' + (p.kanalen.length + 1), functie: 'fixed', standaard: 0, strobe: null, rook: null, kop: 0 }); return teken(); }
      if (b.id === 'chCellen') return cellenMaken();
      if (b.id === 'lookNieuw') { p.looks.push({ naam: 'Nieuwe look', waarden: {} }); return teken(); }
      if (b.dataset.chweg !== undefined) { p.kanalen.splice(Number(b.dataset.chweg), 1); return teken(); }
      if (b.dataset.chop !== undefined) {
        const i = Number(b.dataset.chop); if (i > 0) [p.kanalen[i - 1], p.kanalen[i]] = [p.kanalen[i], p.kanalen[i - 1]]; return teken();
      }
      if (b.dataset.opties !== undefined) { optiesOpen = optiesOpen === Number(b.dataset.opties) ? null : Number(b.dataset.opties); return teken(); }
      if (b.dataset.lookweg !== undefined) { p.looks.splice(Number(b.dataset.lookweg), 1); return teken(); }
    };
    el.oninput = e => {
      const i = e.target, p = P && P[keuze]; if (!p) return;
      if (i.id === 'pfNaam') p.naam = i.value;
      else if (i.id === 'pfFabrikant') p.fabrikant = i.value;
      else if (i.dataset.ch !== undefined) {
        const k = p.kanalen[Number(i.dataset.ch)], veld = i.dataset.k;
        k[veld] = veld === 'naam' || veld === 'functie' ? i.value
          : (i.value === '' && (veld === 'strobe' || veld === 'rook') ? null : Math.max(0, Math.min(veld === 'kop' ? 128 : 255, Number(i.value) || 0)));
      } else if (i.dataset.look !== undefined) {
        const l = p.looks[Number(i.dataset.look)];
        if (i.dataset.k === 'naam') l.naam = i.value; else l.waarden = leesLook(i.value);
      } else if (i.dataset.optietekst !== undefined) p.kanalen[Number(i.dataset.optietekst)].opties = leesOpties(i.value);
      $('#pfOpslaan').disabled = !vuil();
    };
    el.onchange = e => {
      const i = e.target;
      if (i.id === 'pfKeuze') { keuze = i.value; optiesOpen = null; teken(); }
      else if (i.id === 'pfSoort') { P[keuze].soort = i.value; $('#pfOpslaan').disabled = !vuil(); }
      else if (i.dataset.look !== undefined && i.dataset.k === 'waarden') teken();
    };
  },
  state() { if (!vuil()) { P = null; if ($('#pfInhoud')) teken(); } },
};
