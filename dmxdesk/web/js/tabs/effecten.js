// Effecten: kleur, intensiteit en beweging op de beat (voor alle lampen of per laag), looks (laser), auto-show
// en de lichtman (de show volgt het nummer: rustig, opbouw, drop).
import { K, api, doe, esc, $, afremmen, zetShow, toast, invoer, pad, laadState } from '../kern.js';

let laag = null;          // null = alle lampen; anders de naam van een groep (laag)
const LAAGDEEL = /^(kleur|intensiteit|beweging)\./;

// lagen = groepen uit de Patch met lampen die effecten doen
function lagen() {
  const namen = [];
  for (const f of K.S.fixtures) {
    const g = f.groep || 'Overig', eff = f.effecten || {};
    if ((eff.kleur !== false || eff.intensiteit !== false || eff.beweging !== false) && !namen.includes(g)) namen.push(g);
  }
  return namen;
}
const heeftEigen = naam => !!(naam && K.S.show.lagen && K.S.show.lagen[naam] && K.S.show.lagen[naam].eigen);
const cfg = () => heeftEigen(laag) ? K.S.show.lagen[laag] : K.S.show;

async function zet(p, v, herladen = true) {
  if (!(heeftEigen(laag) && LAAGDEEL.test(p))) return zetShow(p, v, herladen);
  const keys = p.split('.'); let o = K.S.show.lagen[laag];
  keys.slice(0, -1).forEach(k => o = o[k] ||= {});
  o[keys[keys.length - 1]] = v;
  try { await api('/api/show', { lagen: { [laag]: pad(p, v) } }); } catch (e) { toast(e.message, true); }
  if (herladen) await laadState();
}

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

const stuurSchuif = afremmen((p, v) => zet(p, v, false), 80);

function laagBlok() {
  const namen = lagen();
  if (laag && !namen.includes(laag)) laag = null;
  return `<div class="blok" style="grid-column:1/-1">
    <div class="rij" style="margin-top:0;flex-wrap:wrap"><b style="margin-right:6px">Laag</b>
      <button data-laag="" class="${laag === null ? 'aan' : ''}">Alle lampen</button>
      ${namen.map(n => `<button data-laag="${esc(n)}" class="${laag === n ? 'aan' : ''}">${esc(n)}${heeftEigen(n) ? ' ●' : ''}</button>`).join('')}
      <span class="vul"></span>
      ${laag && heeftEigen(laag) ? `<button class="stil" id="efLaagWeg">${esc(laag)} volgt weer alle lampen</button>` : ''}</div>
    <p class="hint">${laag === null
      ? 'Patroon, snelheid en kleur voor alle lampen. Kies een laag (groep uit de Patch) om die eigen patronen te geven, bijvoorbeeld de pars een chase en de moving heads een cirkel. ● = laag met eigen patronen.'
      : heeftEigen(laag) ? `Je stelt nu alleen <b>${esc(laag)}</b> in. Een chase loopt binnen deze laag.`
        : `<b>${esc(laag)}</b> volgt nu <b>Alle lampen</b>.`}</p>
    ${laag && !heeftEigen(laag) ? `<button class="primair" id="efLaagEigen">Eigen patronen voor ${esc(laag)}</button>` : ''}
  </div>`;
}

function lichtmanBlok(s) {
  const e = s.energie;
  return `<div class="blok">
      <h2>Lichtman</h2>
      <div class="lichtman"><b id="lmSectie">–</b><span class="hint" id="lmExtra"></span></div>
      <div class="rij"><label>Kick</label><div class="meter" style="flex:1"><i id="lmKick"></i></div></div>
      <div class="rij"><label>Energie</label><div class="meter" style="flex:1"><i id="efMeter"></i></div></div>
      <div class="knoppen twee" style="margin-top:8px">
        <button data-set="energie.aan" data-val="${!e.aan}" class="${e.aan ? 'aan' : ''}" style="grid-column:1/-1">LICHTMAN${e.aan ? ' (AAN): SHOW VOLGT HET NUMMER' : ' (UIT)'}</button>
        <button data-set="energie.flits_bij_drop" data-val="${!e.flits_bij_drop}" class="${e.flits_bij_drop ? 'aan' : ''}">FLITS BIJ DROP${e.flits_bij_drop ? ' (AAN)' : ''}</button>
        <button data-set="energie.opbouw_voor_drop" data-val="${!e.opbouw_voor_drop}" class="${e.opbouw_voor_drop ? 'aan' : ''}">OPBOUW NAAR DE DROP${e.opbouw_voor_drop ? ' (AAN)' : ''}</button>
      </div>
      ${schuif('energie.contrast', 'Rustig ↔ wild', e.contrast ?? 70)}
      <p class="hint">De lichtman luistert vooral naar de <b>kick</b>, niet alleen naar het tempo. Rustig nummer of breakdown:
        gedimd, zachte overgangen, langzaam en een golf over de lampen. Opbouw: steeds sneller op de maat en naar wit, vlak voor de
        drop even donker. Drop: alles op de beat, een knal op elke kick, snel en groot. Hoe verder vooruit hij hoort
        (Spotify-speaker: Geluid → Licht vooruit), hoe beter hij de drop ziet aankomen.
        <b>Rustig ↔ wild</b> bepaalt hoe groot het verschil is.</p>
    </div>`;
}

function teken(el) {
  const S = K.S, s = S.show, M = S.modi, c = cfg();
  const palet = c.kleur.palet || [];
  const eigen = palet.filter(c => !KLEUREN.some(([k]) => k === c));
  const lookProfielen = Object.entries(S.profielen).filter(([pid, p]) => p.looks && p.looks.length && S.fixtures.some(f => f.profiel === pid));
  el.innerHTML = `
  <div class="paginakop"><h1>Effecten</h1><span class="hint">Alles loopt op de beat. Een scène bewaart deze instellingen.</span><span class="vul"></span>
    <button id="efScene" class="primair">Opslaan als scène…</button></div>
  <div class="raster">
    ${laagBlok()}
    ${laag && !heeftEigen(laag) ? '' : `
    <div class="blok">
      <h2>Kleur${laag ? ` · ${esc(laag)}` : ''}</h2>
      ${modusKnoppen('kleur.modus', M.kleur, c.kleur.modus)}
      <h3>Palet (volgorde = nummer)</h3>
      <div class="swatches">
        ${KLEUREN.concat(eigen.map(c => [c, 'eigen'])).map(([c, n]) => { const i = palet.indexOf(c);
          return `<button class="swatch ${i >= 0 ? 'aan' : ''}" style="background:${c}" title="${n}" data-palet="${c}">${i >= 0 ? `<span>${i + 1}</span>` : ''}</button>`; }).join('')}
        <label class="swatch" style="background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red)" title="eigen kleur">
          <input type="color" id="eigenKleur" style="opacity:0;width:100%;height:100%;cursor:pointer"></label>
      </div>
      <div class="rij"><label>Snelheid</label>${keuzelijst('kleur.snelheid', SNELHEDEN, c.kleur.snelheid)}</div>
      ${schuif('kleur.spreiding', 'Spreiding', c.kleur.spreiding)}
    </div>

    <div class="blok">
      <h2>Intensiteit${laag ? ` · ${esc(laag)}` : ''}</h2>
      ${modusKnoppen('intensiteit.modus', M.intensiteit, c.intensiteit.modus)}
      <div class="rij"><label>Snelheid</label>${keuzelijst('intensiteit.snelheid', SNELHEDEN, c.intensiteit.snelheid)}</div>
    </div>

    <div class="blok">
      <h2>Beweging${laag ? ` · ${esc(laag)}` : ' (moving heads)'}</h2>
      ${modusKnoppen('beweging.modus', M.beweging, c.beweging.modus)}
      <div class="rij"><label>Eén ronde duurt</label>${keuzelijst('beweging.snelheid', RONDES, c.beweging.snelheid)}</div>
      ${schuif('beweging.grootte', 'Grootte', c.beweging.grootte)}
      ${schuif('beweging.spreiding', 'Spreiding', c.beweging.spreiding)}
      ${schuif('beweging.pan', 'Midden pan', c.beweging.pan)}
      ${schuif('beweging.tilt', 'Midden tilt', c.beweging.tilt)}
    </div>`}

    ${lichtmanBlok(s)}

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
      <p class="hint">Auto-show kiest zelf steeds nieuwe kleuren, effecten en bewegingen (ook voor lagen met eigen patronen).
        Met de lichtman aan past de keuze bij het moment: rustig = zachte kleuren en golven, drop = chases en flitsen,
        en bij een drop meteen iets nieuws.</p>
    </div>

    <div class="blok">
      <h2>Looks (laser e.d.)</h2>
      ${modusKnoppen('looks.modus', [['uit', 'Uit'], ['vast', 'Vaste look'], ['wissel', 'Automatisch wisselen']], s.looks.modus)}
      <div class="rij"><label>Wissel elke</label>${keuzelijst('looks.elke', [[4, '4 beats'], [8, '8 beats'], [16, '16 beats'], [32, '32 beats']], s.looks.elke)}</div>
      ${lookProfielen.length ? lookProfielen.map(([pid, p]) => `<h3>${esc(p.naam)}</h3><div class="knoppen">
          ${p.looks.map((l, i) => `<button data-look="${esc(pid)}" data-idx="${i}" class="${s.looks.modus === 'vast' && (s.looks.keuze[pid] || 0) === i ? 'aan' : ''}">${esc(l.naam)}</button>`).join('')}</div>`).join('')
        : '<p class="hint">Geen lampen met looks. Een look maak je in de Programmer (Opslaan als look) of in Profielen.</p>'}
    </div>

    ${attribuutBlok(S)}
  </div>`;
  const ek = $('#eigenKleur');
  if (ek) ek.addEventListener('change', e => zet('kleur.palet', (cfg().kleur.palet || []).concat([e.target.value]).slice(-8)));
  energie(K.L);
}

const ELKE = [[1, '1 beat'], [2, '2 beats'], [4, '4 beats'], [8, '8 beats'], [16, '16 beats'], [32, '32 beats']];
function attribuutBlok(S) {
  const lijst = Object.entries(S.attributen || {});
  if (!lijst.length) return '';
  const cfgs = S.show.attributen || {};
  return `<div class="blok" style="grid-column:1/-1">
    <h2>Laser, patronen en programma's</h2>
    <p class="hint">Deze functies van je lampen kan de show zelf aansturen: op de beat wisselen, willekeurig, of harder/sneller als de
      muziek meer energie heeft. Staat een functie op Uit, dan geldt de standaard uit het profiel (of wat je in de Programmer instelt).</p>
    <div class="raster" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">
    ${lijst.map(([fn, info]) => {
      const cfg = cfgs[fn] || {}, modus = cfg.modus || 'uit', keuzes = cfg.keuzes || [];
      const aantal = keuzes.length ? info.opties.filter(o => keuzes.includes(o)).length : info.opties.length;
      return `<div class="kanaalkaart ${modus !== 'uit' ? 'gezet' : ''}">
        <div class="kop"><b>${esc(S.functies[fn] || fn)}</b><span class="hint">${esc(info.lampen.join(', '))}</span></div>
        <div class="opties">${S.modi.attribuut.map(([m, t]) => `<button data-set="attributen.${fn}.modus" data-val='"${m}"' class="${m === modus ? 'aan' : ''}">${esc(t)}</button>`).join('')}</div>
        ${modus === 'wissel' || modus === 'random' ? `<div class="rij"><label>Elke</label>${keuzelijst(`attributen.${fn}.elke`, ELKE, cfg.elke || 4)}</div>` : ''}
        ${info.opties.length > 1 ? `<details><summary class="hint">Welke keuzes doen mee (${aantal} van ${info.opties.length})</summary>
          ${info.opties.map(o => `<label class="rij" style="margin:3px 0;color:var(--tekst)"><input type="checkbox" data-attrkeuze="${fn}" value="${esc(o)}"
            ${!keuzes.length || keuzes.includes(o) ? 'checked' : ''}> ${esc(o)}</label>`).join('')}</details>` : ''}
      </div>`; }).join('')}
    </div></div>`;
}

function energie(L) {
  const st = L && L.s; if (!st) return;
  const bron = Object.values(st.luister || {}).find(i => i.energie !== null && i.energie !== undefined);
  const m = $('#efMeter'); if (!m) return;
  const e = bron ? bron.energie : null, lm = st.lichtman;
  m.style.width = e === null ? '0%' : Math.round(e * 100) + '%';
  $('#lmKick').style.width = lm ? Math.round(lm.kick * 100) + '%' : '0%';
  const s = $('#lmSectie'), x = $('#lmExtra');
  if (!K.S.show.energie.aan) { s.textContent = 'Uit'; s.className = ''; x.textContent = 'De show doet precies wat hieronder is ingesteld.'; return; }
  if (!lm) { s.textContent = 'Hoort nu geen muziek'; s.className = ''; x.textContent = ''; return; }
  s.textContent = lm.flits ? '💥 DROP!' : lm.naam + (lm.sectie === 'opbouw' && lm.opbouw !== null ? ` ${Math.round(lm.opbouw * 100)}%` : '');
  s.className = 'sectie-' + lm.sectie;
  x.textContent = lm.drop_over ? `drop over ${Math.ceil(lm.drop_over)} s` : '';
}

export default {
  id: 'effecten', titel: 'Effecten',
  icoon: '<path d="M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2z"/><path d="M19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7z"/>',
  teken(el) {
    teken(el);
    el.onclick = async e => {
      const b = e.target.closest('button, .swatch'); if (!b) return;
      if (b.dataset.laag !== undefined) { laag = b.dataset.laag || null; return teken(el); }
      if (b.id === 'efLaagEigen') { await doe('/api/show', { lagen: { [laag]: { eigen: true } } }); await laadState(); return teken(el); }
      if (b.id === 'efLaagWeg') { await doe('/api/show', { lagen: { [laag]: null } }); await laadState(); return teken(el); }
      if (b.dataset.set !== undefined && b.dataset.val !== undefined) {
        let v = b.dataset.val; try { v = JSON.parse(v); } catch (x) { /* tekst */ }
        return zet(b.dataset.set, v);
      }
      if (b.id === 'efTap') return doe('/api/tap', {});
      if (b.id === 'efScene') {
        const naam = await invoer('Huidige effecten opslaan als scène', '', 'Kleur, intensiteit, beweging en looks worden bewaard.');
        if (naam) doe('/api/scene', { actie: 'opslaan', naam, inhoud: 'effecten' }, 'Scène opgeslagen');
        return;
      }
      if (b.dataset.bpm) return zetShow('bpm', Math.round(K.S.show.bpm) + Number(b.dataset.bpm));
      if (b.dataset.palet) {
        const c = b.dataset.palet; let p = [...(cfg().kleur.palet || [])];
        p = p.includes(c) ? p.filter(x => x !== c) : p.concat([c]);
        if (!p.length) return toast('Minimaal één kleur nodig', true);
        return zet('kleur.palet', p);
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
      if (i.dataset.attrkeuze) {
        const fn = i.dataset.attrkeuze;
        const gekozen = [...el.querySelectorAll(`[data-attrkeuze="${fn}"]`)].filter(x => x.checked).map(x => x.value);
        if (!gekozen.length) { i.checked = true; return toast('Minimaal één keuze nodig', true); }
        const alle = K.S.attributen[fn].opties.length === gekozen.length;
        return zetShow(`attributen.${fn}.keuzes`, alle ? [] : gekozen);
      }
      if ((i.tagName === 'SELECT' || i.type === 'number') && i.dataset.set) zet(i.dataset.set, i.dataset.num ? Number(i.value) : i.value);
      else if (i.type === 'range' && i.dataset.set) zet(i.dataset.set, Number(i.value));
    };
  },
  live: energie,
};
