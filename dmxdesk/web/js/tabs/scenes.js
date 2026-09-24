// Scènes en cuelijsten: beheren, hernoemen, volgorde, overvloeitijd; cuelijsten die op de beat door scènes lopen.
import { K, api, doe, esc, $, kloon, vraag, invoer, toast } from '../kern.js';

let C = null, cueKeuze = null;     // bewerkbare kopie van de cuelijsten

function vuil() { return C !== null && JSON.stringify(C) !== JSON.stringify(K.S.cuelijsten); }

async function scenesOpslaan(lijst) {
  const nieuw = {};
  for (const [n, sc] of lijst) nieuw[n] = sc;
  K.S.scenes = nieuw;
  await doe('/api/scenes', nieuw);
}

function tekenScenes() {
  const S = K.S, st = K.L.s || S.status;
  const lijst = Object.entries(S.scenes);
  $('#scLijst').innerHTML = lijst.length ? `<div class="scroll"><table>
    <tr><th></th><th>Kleur</th><th>Naam</th><th>Inhoud</th><th>Fade (s)</th><th></th></tr>
    ${lijst.map(([n, sc], i) => `<tr class="${st.scene === n ? 'gekozen' : ''}">
      <td style="white-space:nowrap"><button class="stil icoon" data-omhoog="${i}" ${i ? '' : 'disabled'}>↑</button><button class="stil icoon" data-omlaag="${i}" ${i < lijst.length - 1 ? '' : 'disabled'}>↓</button></td>
      <td style="width:56px"><input type="color" value="${sc.kleur || '#3a3a43'}" data-sckleur="${i}"></td>
      <td><input value="${esc(n)}" data-scnaam="${i}"></td>
      <td class="hint">${[sc.effecten ? 'effecten' : '', Object.keys(sc.vast).length ? Object.keys(sc.vast).length + ' lampen vast' : ''].filter(Boolean).join(' + ') || 'leeg'}</td>
      <td style="width:90px"><input type="number" min="0" max="60" step="0.1" value="${sc.fade}" data-scfade="${i}"></td>
      <td style="white-space:nowrap"><button data-laad="${esc(n)}" class="${st.scene === n ? 'aan' : ''}">Laden</button>
        <button data-overschrijf="${esc(n)}" title="Huidige effecten in deze scène zetten">Bijwerken</button>
        <button class="gevaar" data-weg="${esc(n)}">×</button></td></tr>`).join('')}
  </table></div>` : '<div class="leeg">Nog geen scènes. Sla de huidige effecten op, of maak een scène met vaste kleuren in de Programmer.</div>';
}

function tekenCues() {
  const S = K.S, st = K.L.s || S.status;
  if (C === null) C = kloon(S.cuelijsten);
  const namen = Object.keys(C);
  if (!C[cueKeuze]) cueKeuze = namen[0] || null;
  const cl = C[cueKeuze];
  const scenes = Object.keys(S.scenes);
  const speelt = st.cue && st.cue.lijst === cueKeuze;
  $('#clBlok').innerHTML = `
    <div class="rij" style="margin-top:0">
      <select id="clKeuze" style="flex:1;min-width:160px">${namen.map(n => `<option ${n === cueKeuze ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
      <button id="clNieuw">+ Nieuwe cuelijst</button>
      ${cl ? `<button class="gevaar" id="clWeg">Verwijderen</button>` : ''}
      <button class="primair" id="clOpslaan" ${vuil() ? '' : 'disabled'}>Opslaan</button>
    </div>
    ${!cl ? '<div class="leeg">Een cuelijst speelt scènes na elkaar af, bijvoorbeeld elke 16 beats een andere. Maak er een met + Nieuwe cuelijst.</div>' : `
      <div class="rij"><label>Naam</label><input id="clNaam" value="${esc(cueKeuze)}" style="flex:1">
        <select id="clEenheid"><option value="beats" ${cl.eenheid === 'beats' ? 'selected' : ''}>duur in beats</option>
          <option value="seconden" ${cl.eenheid === 'seconden' ? 'selected' : ''}>duur in seconden</option></select>
        <label class="check"><input type="checkbox" id="clHerhaal" ${cl.herhalen ? 'checked' : ''}> herhalen</label>
        <button id="clSpeel" class="${speelt ? 'aan' : ''}">${speelt ? '■ Stop' : '▶ Start'}</button></div>
      <div class="scroll"><table><tr><th>#</th><th>Scène</th><th>Duur (${cl.eenheid === 'seconden' ? 's' : 'beats'})</th><th>Fade (s)</th><th></th></tr>
      ${cl.stappen.map((s, i) => `<tr class="${speelt && st.cue.stap === i ? 'gekozen' : ''}"><td class="nr">${i + 1}</td>
        <td><select data-stap="${i}" data-k="scene">${scenes.map(n => `<option ${n === s.scene ? 'selected' : ''}>${esc(n)}</option>`).join('')}
          ${scenes.includes(s.scene) ? '' : `<option selected>${esc(s.scene)} (bestaat niet)</option>`}</select></td>
        <td style="width:100px"><input type="number" min="0.25" step="0.25" value="${s.duur}" data-stap="${i}" data-k="duur"></td>
        <td style="width:90px"><input type="number" min="0" max="60" step="0.1" value="${s.fade}" data-stap="${i}" data-k="fade"></td>
        <td style="white-space:nowrap"><button class="stil icoon" data-stapop="${i}">↑</button><button class="stil icoon" data-stapneer="${i}">↓</button>
          ${speelt ? `<button class="stil" data-gastap="${i}">Ga</button>` : ''}<button class="stil icoon" data-stapweg="${i}">×</button></td></tr>`).join('')}
      </table></div>
      <div class="rij"><button id="clStap" ${scenes.length ? '' : 'disabled'}>+ Stap</button>
        <button id="clAlle" ${scenes.length ? '' : 'disabled'}>Alle scènes toevoegen</button>
        ${scenes.length ? '' : '<span class="hint">Maak eerst scènes.</span>'}</div>`}`;
}

async function cuesOpslaan() {
  try { await api('/api/cuelijsten', C); toast('Cuelijsten opgeslagen'); K.S.cuelijsten = kloon(C); tekenCues(); }
  catch (e) { toast(e.message, true); }
}

export default {
  id: 'scenes', titel: 'Scènes',
  icoon: '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 12l10 5 10-5"/><path d="M2 17l10 5 10-5"/>',
  vuil,
  teken(el) {
    C = null;
    el.innerHTML = `<div class="paginakop"><h1>Scènes</h1><span class="vul"></span>
        <button id="scNieuw" class="primair">Huidige effecten opslaan als scène…</button></div>
      <div class="stapel"><div class="blok"><h2>Scènes</h2><div id="scLijst"></div>
        <p class="hint">Sneltoetsen 1–9 en 0 laden de eerste tien scènes. Esc laat de scène los.</p></div>
      <div class="blok"><h2>Cuelijsten</h2><div id="clBlok"></div></div></div>`;
    tekenScenes(); tekenCues();

    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b || b.disabled) return;
      const S = K.S, lijst = Object.entries(S.scenes);
      if (b.id === 'scNieuw') {
        const naam = await invoer('Huidige effecten opslaan als scène', '', 'Kleur, intensiteit, beweging en looks worden bewaard.');
        if (naam) doe('/api/scene', { actie: 'opslaan', naam, inhoud: 'effecten' }, 'Scène opgeslagen');
      } else if (b.dataset.laad) doe('/api/scene', { actie: 'laden', naam: b.dataset.laad });
      else if (b.dataset.overschrijf) {
        const sc = S.scenes[b.dataset.overschrijf];
        if (await vraag(`De effecten in "${b.dataset.overschrijf}" vervangen door de huidige?`, 'Bijwerken'))
          doe('/api/scene', { actie: 'opslaan', naam: b.dataset.overschrijf, inhoud: Object.keys(sc.vast).length ? 'beide' : 'effecten',
            fade: sc.fade, kleur: sc.kleur }, 'Scène bijgewerkt');
      } else if (b.dataset.weg) {
        if (await vraag(`Scène "${b.dataset.weg}" verwijderen?`, 'Verwijderen', true)) doe('/api/scene', { actie: 'verwijderen', naam: b.dataset.weg });
      } else if (b.dataset.omhoog || b.dataset.omlaag) {
        const i = Number(b.dataset.omhoog ?? b.dataset.omlaag), j = b.dataset.omhoog ? i - 1 : i + 1;
        [lijst[i], lijst[j]] = [lijst[j], lijst[i]];
        await scenesOpslaan(lijst); tekenScenes();
      }
      // cuelijsten
      else if (b.id === 'clNieuw') {
        const naam = await invoer('Naam van de nieuwe cuelijst', 'Cuelijst ' + (Object.keys(C).length + 1));
        if (!naam) return;
        if (C[naam]) return toast('Die naam bestaat al', true);
        C[naam] = { stappen: [], eenheid: 'beats', herhalen: true }; cueKeuze = naam; tekenCues();
      } else if (b.id === 'clWeg') {
        if (await vraag(`Cuelijst "${cueKeuze}" verwijderen?`, 'Verwijderen', true)) { delete C[cueKeuze]; cueKeuze = null; await cuesOpslaan(); }
      } else if (b.id === 'clOpslaan') cuesOpslaan();
      else if (b.id === 'clSpeel') {
        const st = K.L.s;
        if (st && st.cue && st.cue.lijst === cueKeuze) doe('/api/cue', { actie: 'stop' });
        else { if (vuil()) await cuesOpslaan(); doe('/api/cue', { actie: 'start', naam: cueKeuze }); }
      } else if (b.id === 'clStap') {
        const sc = Object.keys(S.scenes);
        const vorige = C[cueKeuze].stappen.at(-1);
        C[cueKeuze].stappen.push({ scene: sc[(sc.indexOf(vorige?.scene) + 1) % sc.length], duur: vorige?.duur || 16, fade: vorige?.fade ?? 0 });
        tekenCues();
      } else if (b.id === 'clAlle') {
        Object.keys(S.scenes).forEach(n => C[cueKeuze].stappen.push({ scene: n, duur: 16, fade: 0 })); tekenCues();
      } else if (b.dataset.stapweg) { C[cueKeuze].stappen.splice(Number(b.dataset.stapweg), 1); tekenCues(); }
      else if (b.dataset.stapop || b.dataset.stapneer) {
        const st = C[cueKeuze].stappen, i = Number(b.dataset.stapop ?? b.dataset.stapneer), j = b.dataset.stapop ? i - 1 : i + 1;
        if (j >= 0 && j < st.length) { [st[i], st[j]] = [st[j], st[i]]; tekenCues(); }
      } else if (b.dataset.gastap) doe('/api/cue', { actie: 'start', naam: cueKeuze, stap: Number(b.dataset.gastap) });
    };
    el.onchange = async e => {
      const i = e.target, S = K.S, lijst = Object.entries(S.scenes);
      if (i.dataset.scnaam !== undefined) {
        const nr = Number(i.dataset.scnaam), nieuw = i.value.trim();
        if (!nieuw || (S.scenes[nieuw] && lijst[nr][0] !== nieuw)) { toast('Lege of bestaande naam', true); return tekenScenes(); }
        const oud = lijst[nr][0];
        lijst[nr][0] = nieuw;
        for (const cl of Object.values(C)) cl.stappen.forEach(s => { if (s.scene === oud) s.scene = nieuw; });
        await scenesOpslaan(lijst);
        if (vuil()) await cuesOpslaan();
      } else if (i.dataset.sckleur !== undefined) { lijst[Number(i.dataset.sckleur)][1].kleur = i.value; await scenesOpslaan(lijst); }
      else if (i.dataset.scfade !== undefined) { lijst[Number(i.dataset.scfade)][1].fade = Math.max(0, Number(i.value) || 0); await scenesOpslaan(lijst); }
      else if (i.id === 'clKeuze') { cueKeuze = i.value; tekenCues(); }
      else if (i.id === 'clNaam') {
        const nieuw = i.value.trim();
        if (!nieuw || (C[nieuw] && nieuw !== cueKeuze)) { toast('Lege of bestaande naam', true); return tekenCues(); }
        const nieuwC = {}; for (const [n, v] of Object.entries(C)) nieuwC[n === cueKeuze ? nieuw : n] = v;
        C = nieuwC; cueKeuze = nieuw; tekenCues();
      } else if (i.id === 'clEenheid') { C[cueKeuze].eenheid = i.value; tekenCues(); }
      else if (i.id === 'clHerhaal') { C[cueKeuze].herhalen = i.checked; tekenCues(); }
      else if (i.dataset.stap !== undefined) {
        const s = C[cueKeuze].stappen[Number(i.dataset.stap)];
        s[i.dataset.k] = i.dataset.k === 'scene' ? i.value : Math.max(0, Number(i.value) || 0);
        tekenCues();
      }
    };
  },
  state() { if (!$('#scLijst')) return; tekenScenes(); if (!vuil()) { C = null; } tekenCues(); },
  live(L) {
    const st = L.s, sleutel = `${st.scene}|${st.cue ? st.cue.lijst + st.cue.stap : ''}`;
    if (sleutel !== this._laatst && $('#scLijst')) {
      this._laatst = sleutel;
      const actief = document.activeElement;
      if (!(actief && /INPUT|SELECT/.test(actief.tagName))) { tekenScenes(); tekenCues(); }
    }
  },
};
