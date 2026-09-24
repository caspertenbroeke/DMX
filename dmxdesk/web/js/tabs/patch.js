// Patch: welke lampen er zijn, op welk DMX-adres, in welke groep. Toevoegen uit de bibliotheek.
import { K, api, doe, esc, $, $$, kloon, dialoog, toast, vraag, laadState, adresBereik, overlapt, vrijAdres, afremmen } from '../kern.js';

let F = null;           // bewerkbare kopie van de lampen
let open = new Set();   // rijen met 'meer' opengeklapt
const GROEP = { par: 'Pars', moving: 'Moving heads', bar: 'LED-bars', laser: 'Lasers', rook: 'Rook', strobe: 'Strobes', dimmer: 'Dimmers', overig: 'Overig' };
const HOOGTE = { moving: 35, laser: 20, par: 70, bar: 88, rook: 92, strobe: 25, dimmer: 60, overig: 60 };

const vuil = () => F !== null && JSON.stringify(F) !== JSON.stringify(K.S.fixtures);

function dip(adres) {
  // DIP-schakelaars (1 = aan) voor lampen zonder display: schakelaar n telt 2^(n-1)
  return Array.from({ length: 9 }, (_, i) => (adres >> i) & 1 ? '▮' : '▯').join('');
}

function teken() {
  const S = K.S;
  if (F === null) F = kloon(S.fixtures);
  const profOpties = pid => Object.entries(S.profielen).sort((a, b) => a[1].naam.localeCompare(b[1].naam))
    .map(([id, p]) => `<option value="${esc(id)}" ${id === pid ? 'selected' : ''}>${esc(p.naam)} (${p.kanalen.length} ch)</option>`).join('');
  const universes = [...new Set(F.map(f => Number(f.universe)))].sort((a, b) => a - b);
  $('#ptTabel').innerHTML = F.length ? `<div class="scroll"><table>
    <tr><th>Naam</th><th>Profiel</th><th title="Universe">U</th><th>Adres</th><th>Groep</th>
      <th title="Volgt kleur / intensiteit / beweging">Effecten</th><th title="Doet mee met STROBE en BLINDER">Strobe</th><th></th></tr>
    ${F.map((f, i) => {
      const [a, b] = adresBereik(f, S), fout = overlapt(F, i, S), p = S.profielen[f.profiel];
      const bew = p && p.kanalen.some(k => k.functie === 'pan' || k.functie === 'tilt');
      return `<tr>
        <td style="min-width:130px"><input data-i="${i}" data-k="naam" value="${esc(f.naam)}"></td>
        <td style="min-width:200px"><select data-i="${i}" data-k="profiel">${profOpties(f.profiel)}</select></td>
        <td style="width:62px"><input type="number" min="1" max="64" data-i="${i}" data-k="universe" value="${f.universe}"></td>
        <td style="width:150px;white-space:nowrap"><input type="number" min="1" max="512" data-i="${i}" data-k="adres" value="${f.adres}" style="width:70px">
          <span class="adres nr ${fout ? 'fout' : 'hint'}" title="${esc(fout || 'kanalen ' + a + '–' + b)}">${fout ? '⚠ ' : ''}–${b}</span></td>
        <td style="min-width:110px"><input data-i="${i}" data-k="groep" value="${esc(f.groep)}" list="groepLijst"></td>
        <td style="white-space:nowrap">${['kleur', 'intensiteit', 'beweging'].map(s => `<input type="checkbox" title="${s}" data-i="${i}" data-k="effecten.${s}" ${f.effecten[s] ? 'checked' : ''}>`).join(' ')}</td>
        <td><input type="checkbox" data-i="${i}" data-k="strobe" ${f.strobe ? 'checked' : ''}></td>
        <td style="white-space:nowrap"><button class="stil" data-zoek="${f.id}" title="Laat deze lamp 4 seconden knipperen: zo zie je of adres, kabel en DMX-modus kloppen">Zoek</button>
          <button class="stil icoon" data-meer="${f.id}" title="Meer">${open.has(f.id) ? '▴' : '▾'}</button>
          <button class="stil icoon" data-kopie="${i}" title="Dupliceren">⧉</button><button class="stil icoon" data-weg="${i}" title="Verwijderen">×</button></td>
      </tr>${open.has(f.id) ? `<tr><td colspan="8"><div class="velden" style="padding:6px 0 10px">
        ${bew ? `<label>Pan min / max<span class="rij" style="margin:0"><input type="number" min="0" max="255" data-i="${i}" data-k="pan_min" value="${f.pan_min}">
            <input type="number" min="0" max="255" data-i="${i}" data-k="pan_max" value="${f.pan_max}"></span></label>
          <label>Tilt min / max<span class="rij" style="margin:0"><input type="number" min="0" max="255" data-i="${i}" data-k="tilt_min" value="${f.tilt_min}">
            <input type="number" min="0" max="255" data-i="${i}" data-k="tilt_max" value="${f.tilt_max}"></span></label>
          <label class="check"><input type="checkbox" data-i="${i}" data-k="pan_omkeren" ${f.pan_omkeren ? 'checked' : ''}> Pan omkeren</label>
          <label class="check"><input type="checkbox" data-i="${i}" data-k="tilt_omkeren" ${f.tilt_omkeren ? 'checked' : ''}> Tilt omkeren</label>` : ''}
        <label>Plek links→rechts / achter→voor<span class="rij" style="margin:0"><input type="number" min="0" max="100" data-i="${i}" data-k="x" value="${f.x}">
          <input type="number" min="0" max="100" data-i="${i}" data-k="y" value="${f.y}"></span></label>
        <label>DIP-schakelaars (1 → 9)<span class="nr" style="font-size:18px;letter-spacing:2px;color:var(--tekst)">${dip(Number(f.adres))}</span></label>
      </div></td></tr>` : ''}`; }).join('')}
  </table></div>
  <datalist id="groepLijst">${[...new Set(F.map(f => f.groep))].map(g => `<option value="${esc(g)}">`).join('')}</datalist>
  <p class="hint">${F.length} lampen · ${universes.map(u => `universe ${u}: ${F.filter(f => Number(f.universe) === u).reduce((s, f) => s + (S.profielen[f.profiel]?.kanalen.length || 0), 0)} kanalen`).join(' · ')}</p>`
    : '<div class="leeg">Nog geen lampen. Voeg ze toe uit de bibliotheek met <b>+ Lamp toevoegen</b>.</div>';
  $('#ptTips').innerHTML = `<h2>Doet een lamp niets?</h2><ol class="hint" style="line-height:1.7">
    <li><b>Adres:</b> het adres op de lamp (display of DIP-schakelaars) moet hetzelfde zijn als hier. Met <b>Zoek</b> knippert de lamp op dit adres.</li>
    <li><b>DMX-modus:</b> zet de lamp in DMX-modus met precies zoveel kanalen als het profiel (niet in auto- of geluidsmodus).</li>
    <li><b>Kabel:</b> bovenin moet <b>DMX ok</b> groen staan. Zo niet: tabblad Uitgangen. Kies daar "USB-DMX-kabel (herkent zelf het type)".</li>
    <li><b>Laatste lamp in de rij:</b> bij lange kabels helpt een DMX-eindweerstand (terminator) in de laatste lamp.</li>
    <li><b>Kijk in de Monitor</b> welke waarden er echt naar buiten gaan, en in de <b>Programmer</b> kun je elk kanaal met de hand zetten.</li></ol>`;
  const knop = $('#ptOpslaan'); if (knop) knop.disabled = !vuil();
}

async function opslaan() {
  try { await api('/api/fixtures', F); await laadState(true); F = kloon(K.S.fixtures); teken(); toast('Patch opgeslagen'); }
  catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------------------ toevoegen uit de bibliotheek
function wizard() {
  const S = K.S;
  let keuze = null;      // {bron: 'bib'|'show', sleutel|pid, modi: [{modus, profiel}], modus: index}
  const d = dialoog({
    titel: 'Lampen toevoegen', breed: true,
    html: `<div class="rij" style="margin-top:0">
        <input id="wzZoek" placeholder="Zoek op merk of model, bijv. 'ADJ mega par' of 'moving head'" style="flex:1;min-width:220px">
        <select id="wzSoort"><option value="">alle soorten</option>${Object.entries(S.soorten).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select>
        <select id="wzBron"><option value="bib">Bibliotheek (${S.bibliotheek.aantal})</option><option value="show">In deze show (${Object.keys(S.profielen).length})</option></select></div>
      <div class="zoekresultaten" id="wzLijst"></div>
      <div id="wzKeuze" style="margin-top:12px"></div>
      <p class="hint">Staat je lamp er niet bij? Kijk op <a href="https://open-fixture-library.org" target="_blank" rel="noopener">open-fixture-library.org</a>
        of neem een QLC+-bestand (.qxf): die lees je in bij Profielen → Importeren. Of kies een generiek profiel met hetzelfde aantal kanalen.</p>`,
    knoppen: [{ tekst: 'Annuleren' }, { tekst: 'Toevoegen', klasse: 'primair', actie: () => toevoegen() }],
  });
  const lijst = $('#wzLijst', d.el), keuzeEl = $('#wzKeuze', d.el);

  const zoek = afremmen(async () => {
    const term = $('#wzZoek', d.el).value, soort = $('#wzSoort', d.el).value;
    if ($('#wzBron', d.el).value === 'show') {
      const res = Object.entries(S.profielen).filter(([, p]) => (!soort || p.soort === soort) &&
        `${p.fabrikant} ${p.naam}`.toLowerCase().includes(term.toLowerCase()));
      lijst.innerHTML = res.map(([pid, p]) => `<button data-pid="${esc(pid)}"><span class="label-soort">${esc(S.soorten[p.soort] || p.soort)}</span>
        <span><b>${esc(p.naam)}</b> ${p.fabrikant ? `<span class="hint">${esc(p.fabrikant)}</span>` : ''}</span><small>${p.kanalen.length} kanalen</small></button>`).join('')
        || '<p class="hint" style="padding:10px">Niets gevonden.</p>';
      return;
    }
    try {
      const r = await api(`/api/bibliotheek?zoek=${encodeURIComponent(term)}&soort=${encodeURIComponent(soort)}`);
      lijst.innerHTML = r.resultaten.map(i => `<button data-sleutel="${esc(i.sleutel)}"><span class="label-soort">${esc(S.soorten[i.soort] || i.soort)}</span>
        <span><span class="hint">${esc(i.fabrikant)}</span> <b>${esc(i.naam)}</b></span>
        <small>${i.modi.length > 1 ? i.modi.length + ' modi · ' : ''}${[...new Set(i.modi.map(m => m.kanalen))].slice(0, 4).join('/')} ch</small></button>`).join('')
        + (r.totaal > r.resultaten.length ? `<p class="hint" style="padding:8px 12px">…en nog ${r.totaal - r.resultaten.length}. Zoek specifieker.</p>` : '')
        || '<p class="hint" style="padding:10px">Niets gevonden.</p>';
    } catch (e) { lijst.innerHTML = `<p class="hint fout" style="padding:10px">${esc(e.message)}</p>`; }
  }, 180);

  function tekenKeuze() {
    if (!keuze) { keuzeEl.innerHTML = ''; return; }
    const prof = keuze.modi[keuze.modus].profiel;
    const n = prof.kanalen.length;
    const aantal = Math.max(1, Number($('#wzAantal', d.el)?.value) || 1);
    const universe = Number($('#wzUniverse', d.el)?.value || (F.length ? F.at(-1).universe : 1));
    const adres = vrijAdres(F, universe, n * aantal);
    const basis = prof.naam.split(' – ')[0];
    keuzeEl.innerHTML = `<div class="blok"><h2>${esc(prof.fabrikant ? prof.fabrikant + ' ' : '')}${esc(basis)}</h2>
      ${keuze.modi.length > 1 ? `<p class="hint">Kies de DMX-modus die op de lamp is ingesteld (zie het display of de handleiding):</p>
        <div class="modi">${keuze.modi.map((m, i) => `<button data-modus="${i}" class="${i === keuze.modus ? 'aan' : ''}">${esc(m.modus)} · ${m.profiel.kanalen.length} ch</button>`).join('')}</div>` : ''}
      <div class="velden" style="margin-top:12px">
        <label>Aantal<input id="wzAantal" type="number" min="1" max="64" value="${aantal}"></label>
        <label>Universe<input id="wzUniverse" type="number" min="1" max="64" value="${universe}"></label>
        <label>Startadres<input id="wzAdres" type="number" min="1" max="512" value="${adres || 1}"></label>
        <label>Groep<input id="wzGroep" value="${esc($('#wzGroep', d.el)?.value || GROEP[prof.soort] || 'Overig')}" list="groepLijst"></label>
        <label>Naam<input id="wzNaam" value="${esc(basis)}"></label>
      </div>
      <p class="hint"><b>Belangrijk:</b> zet de lamp in de DMX-modus met <b>${n} kanalen</b>. Staat er al een adres op de lamp
        (display of DIP-schakelaars)? Vul dát hier in als startadres. Anders: zet het adres hieronder op de lamp.</p>
      <p class="hint ${adres ? '' : 'fout'}">${adres ? `${n} kanalen per lamp. ${aantal > 1 ? `De lampen krijgen opeenvolgende adressen (${adres}, ${adres + n}, …, ${adres + (aantal - 1) * n}).` : ''}`
        : `In universe ${universe} is geen plek meer voor ${aantal} × ${n} kanalen. Kies een andere universe.`}</p>
      <details><summary class="hint">Kanalen bekijken</summary><ol class="hint">${prof.kanalen.map(k => `<li>${esc(k.naam)} – ${esc(S.functies[k.functie] || k.functie)}${k.kop ? ' (cel ' + k.kop + ')' : ''}</li>`).join('')}</ol></details></div>`;
  }

  lijst.onclick = async e => {
    const b = e.target.closest('button'); if (!b) return;
    $$('button', lijst).forEach(x => x.classList.toggle('aan', x === b));
    if (b.dataset.pid) keuze = { bron: 'show', pid: b.dataset.pid, modi: [{ modus: '', profiel: S.profielen[b.dataset.pid] }], modus: 0 };
    else {
      try { keuze = { bron: 'bib', modi: await api('/api/bibliotheek/profielen?sleutel=' + encodeURIComponent(b.dataset.sleutel)), modus: 0 }; }
      catch (x) { return toast(x.message, true); }
    }
    tekenKeuze();
  };
  keuzeEl.onclick = e => { const b = e.target.closest('[data-modus]'); if (b) { keuze.modus = Number(b.dataset.modus); tekenKeuze(); } };
  keuzeEl.onchange = e => { if (e.target.id === 'wzUniverse' || e.target.id === 'wzAantal') tekenKeuze(); };
  $('#wzZoek', d.el).oninput = zoek; $('#wzSoort', d.el).onchange = zoek; $('#wzBron', d.el).onchange = zoek;
  zoek();

  async function toevoegen() {
    if (!keuze) { toast('Kies eerst een lamp', true); return false; }
    const prof = keuze.modi[keuze.modus].profiel;
    let pid = keuze.pid;
    if (keuze.bron === 'bib') {
      const r = await doe('/api/profiel-toevoegen', { profiel: prof });
      if (!r) return false;
      pid = r.id;
      await laadState(true);
    }
    const aantal = Math.max(1, Math.min(64, Number($('#wzAantal', d.el).value) || 1));
    const universe = Math.max(1, Math.min(64, Number($('#wzUniverse', d.el).value) || 1));
    let adres = Math.max(1, Number($('#wzAdres', d.el).value) || 1);
    const naam = $('#wzNaam', d.el).value.trim() || 'Lamp', groep = $('#wzGroep', d.el).value.trim() || 'Overig';
    const n = prof.kanalen.length;
    if (adres + n * aantal - 1 > 512) { toast(`Past niet: ${aantal} × ${n} kanalen vanaf adres ${adres} gaat voorbij 512. Kies een andere universe.`, true); return false; }
    const botsing = F.find(f => Number(f.universe) === universe && (() => { const [a, b] = adresBereik(f); return a <= adres + n * aantal - 1 && adres <= b; })());
    if (botsing) { toast(`Adres ${adres}–${adres + n * aantal - 1} is (deels) bezet door ${botsing.naam}. Kies een ander startadres.`, true); return false; }
    let id = Math.max(0, ...F.map(f => f.id), ...K.S.fixtures.map(f => f.id)) + 1;
    const geenEffecten = prof.soort === 'rook' || prof.soort === 'laser';
    for (let i = 0; i < aantal; i++) {
      F.push({ id: id++, naam: aantal > 1 ? `${naam} ${i + 1}` : naam, profiel: pid, universe, adres, groep,
        x: aantal > 1 ? Math.round(10 + 80 * i / (aantal - 1)) : 50, y: HOOGTE[prof.soort] ?? 60, breedte: prof.soort === 'bar' ? 20 : 10,
        strobe: prof.soort !== 'rook', effecten: { kleur: !geenEffecten, intensiteit: !geenEffecten, beweging: !geenEffecten },
        pan_min: 0, pan_max: 255, tilt_min: 0, tilt_max: 255, pan_omkeren: false, tilt_omkeren: false });
      adres += n;
    }
    await opslaan();
    return true;
  }
}

export default {
  id: 'patch', titel: 'Patch',
  icoon: '<path d="M9 2v6M15 2v6"/><path d="M6 8h12v4a6 6 0 0 1-12 0z"/><path d="M12 18v4"/>',
  vuil,
  teken(el) {
    F = null;
    el.innerHTML = `<div class="paginakop"><h1>Patch</h1><span class="hint">Welke lampen er zijn en op welk DMX-adres ze staan.</span><span class="vul"></span>
        <button id="ptNieuw" class="primair">+ Lamp toevoegen</button><button id="ptHerstel">Wijzigingen ongedaan maken</button>
        <button id="ptOpslaan" class="primair" disabled>Opslaan</button></div>
      <div class="blok" id="ptTabel"></div><div class="blok" id="ptTips" style="margin-top:14px"></div>`;
    teken();
    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.id === 'ptNieuw') wizard();
      else if (b.id === 'ptOpslaan') opslaan();
      else if (b.id === 'ptHerstel') { F = null; teken(); }
      else if (b.dataset.zoek) {
        if (vuil()) return toast('Sla eerst op: Zoek gebruikt het opgeslagen adres', true);
        const f = K.S.fixtures.find(x => x.id === Number(b.dataset.zoek));
        if (await doe('/api/zoek', { fixture: Number(b.dataset.zoek) }))
          toast(`${f.naam} knippert nu (universe ${f.universe}, adres ${f.adres}). Knippert er niets? Zie de tips onderaan.`);
      }
      else if (b.dataset.meer) { const id = Number(b.dataset.meer); open.has(id) ? open.delete(id) : open.add(id); teken(); }
      else if (b.dataset.kopie !== undefined) {
        const f = kloon(F[Number(b.dataset.kopie)]);
        f.id = Math.max(0, ...F.map(x => x.id)) + 1;
        f.naam = f.naam.replace(/\d+$/, m => String(Number(m) + 1)); if (f.naam === F[Number(b.dataset.kopie)].naam) f.naam += ' 2';
        f.adres = vrijAdres(F, f.universe, (K.S.profielen[f.profiel]?.kanalen.length) || 1) || f.adres;
        f.x = Math.min(100, f.x + 8);
        F.splice(Number(b.dataset.kopie) + 1, 0, f); teken();
      } else if (b.dataset.weg !== undefined) {
        const f = F[Number(b.dataset.weg)];
        if (await vraag(`"${f.naam}" verwijderen?`, 'Verwijderen', true)) { F.splice(Number(b.dataset.weg), 1); teken(); }
      }
    };
    el.oninput = e => {
      const i = e.target; if (i.dataset.i === undefined) return;
      const f = F[Number(i.dataset.i)], k = i.dataset.k;
      const v = i.type === 'checkbox' ? i.checked : (i.type === 'number' ? Number(i.value) : i.value);
      if (k.startsWith('effecten.')) f.effecten[k.split('.')[1]] = v; else f[k] = v;
      $('#ptOpslaan').disabled = !vuil();
    };
    el.onchange = e => { if (['profiel', 'adres', 'universe'].includes(e.target.dataset.k)) teken(); };
  },
  state() { if (!vuil()) { F = null; if ($('#ptTabel')) teken(); } },
};
