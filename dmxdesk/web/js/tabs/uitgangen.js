// Uitgangen: USB-DMX-dongles en netwerk (Art-Net, sACN). Meerdere universes, elk naar een eigen uitgang.
import { K, api, esc, $, kloon, toast, vraag, laadState } from '../kern.js';

let U = null, poorten = [];
const vuil = () => U !== null && JSON.stringify(U) !== JSON.stringify(K.S.uitgangen);
const SERIEEL = new Set(['opendmx', 'enttecpro']);
const UITLEG = {
  opendmx: 'Goedkope USB-DMX-kabel met FTDI-chip (Enttec Open DMX en klonen). De computer maakt het DMX-signaal zelf.',
  enttecpro: 'Enttec DMX USB Pro, DMXking ultraDMX en andere "Pro"-compatibele dongles.',
  artnet: 'Via het netwerk naar een Art-Net-node. Leeg IP-adres = broadcast naar het hele netwerk. Art-Net-universes tellen vanaf 0.',
  sacn: 'Via het netwerk (E1.31). Leeg IP-adres = multicast. sACN-universes tellen vanaf 1.',
};

async function zoekPoorten() {
  try { poorten = await api('/api/poorten'); } catch (e) { poorten = []; }
  if ($('#uiLijst')) teken();
}

function teken() {
  const S = K.S, st = (K.L.s || S.status).uitgangen || {};
  if (U === null) U = kloon(S.uitgangen);
  $('#uiLijst').innerHTML = U.length ? U.map((u, i) => {
    const s = st[u.id] || {};
    const poortOpties = [['auto', 'Automatisch zoeken'], ...poorten.map(p => [p.poort, `${p.poort} – ${p.naam}${p.ftdi ? ' (FTDI)' : ''}`])];
    if (u.poort && !poortOpties.some(([p]) => p === u.poort)) poortOpties.push([u.poort, u.poort + ' (niet gevonden)']);
    return `<div class="blok" style="margin-bottom:12px">
      <div class="rij" style="margin-top:0"><i class="dot ${s.ok ? 'ok' : ''}" data-dot="${u.id}"></i>
        <input data-i="${i}" data-k="naam" value="${esc(u.naam)}" style="font-weight:700;flex:1;min-width:160px">
        <label class="check" style="color:var(--tekst)"><input type="checkbox" data-i="${i}" data-k="aan" ${u.aan ? 'checked' : ''}> aan</label>
        <button class="stil" data-weg="${i}">Verwijderen</button></div>
      <p class="hint" data-status="${u.id}">${esc(s.tekst || (u.aan ? '…' : 'uit'))}${s.fps ? ` · ${s.fps} frames/s` : ''}</p>
      <div class="velden">
        <label>Soort<select data-i="${i}" data-k="soort">${Object.entries(S.uitgang_soorten).map(([k, v]) => `<option value="${k}" ${k === u.soort ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
        <label>DMXDesk-universe<input type="number" min="1" max="64" data-i="${i}" data-k="universe" value="${u.universe}"></label>
        ${SERIEEL.has(u.soort) ? `<label>Poort<select data-i="${i}" data-k="poort">${poortOpties.map(([p, t]) => `<option value="${esc(p)}" ${p === u.poort ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label>`
          : `<label>IP-adres (leeg = ${u.soort === 'artnet' ? 'broadcast' : 'multicast'})<input data-i="${i}" data-k="ip" value="${esc(u.ip)}" placeholder="${u.soort === 'artnet' ? '255.255.255.255' : 'multicast'}"></label>
             <label>${u.soort === 'artnet' ? 'Art-Net-universe (vanaf 0)' : 'sACN-universe (vanaf 1)'}<input type="number" min="0" max="63999" data-i="${i}" data-k="net_universe" value="${u.net_universe}"></label>`}
      </div><p class="hint">${UITLEG[u.soort]}</p></div>`; }).join('')
    : '<div class="leeg">Geen uitgangen: DMXDesk rekent wel, maar stuurt niets naar buiten. Voeg er een toe.</div>';
  $('#uiOpslaan').disabled = !vuil();
}

export default {
  id: 'uitgangen', titel: 'Uitgangen',
  icoon: '<rect x="3" y="7" width="18" height="10" rx="2"/><circle cx="8" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/><path d="M12 17v4M8 21h8"/>',
  vuil,
  teken(el) {
    U = null;
    el.innerHTML = `<div class="paginakop"><h1>Uitgangen</h1><span class="hint">Waar het DMX-signaal naartoe gaat.</span><span class="vul"></span>
        <button id="uiZoek">Poorten opnieuw zoeken</button><button id="uiOpslaan" class="primair" disabled>Opslaan</button></div>
      <div class="rij" style="margin-top:0">${Object.entries(K.S.uitgang_soorten).map(([k, v]) => `<button data-nieuw="${k}">+ ${esc(v)}</button>`).join('')}</div>
      <div id="uiLijst"></div>
      <p class="hint">Tip: Windows vraagt bij de eerste start of DMXDesk het netwerk mag gebruiken: kies <b>Toestaan</b> (nodig voor Art-Net/sACN en je telefoon).
        Een USB-dongle met FTDI-chip heeft op Windows soms de FTDI-driver nodig (ftdichip.com, "VCP drivers").</p>`;
    teken(); zoekPoorten();
    el.onclick = async e => {
      const b = e.target.closest('button'); if (!b || b.disabled) return;
      if (b.id === 'uiZoek') { await zoekPoorten(); toast(poorten.length ? `${poorten.length} poort(en) gevonden` : 'Geen seriële poorten gevonden'); }
      else if (b.id === 'uiOpslaan') {
        try { await api('/api/uitgangen', U); await laadState(); U = kloon(K.S.uitgangen); teken(); toast('Uitgangen opgeslagen'); }
        catch (x) { toast(x.message, true); }
      } else if (b.dataset.nieuw) {
        const soort = b.dataset.nieuw, id = Math.max(0, ...U.map(u => u.id)) + 1;
        const universe = Math.max(1, ...K.S.fixtures.map(f => f.universe)) > U.length ? U.length + 1 : 1;
        U.push({ id, naam: K.S.uitgang_soorten[soort], soort, universe, poort: 'auto', ip: '', net_universe: soort === 'artnet' ? universe - 1 : universe, aan: true });
        teken();
      } else if (b.dataset.weg !== undefined) {
        if (await vraag(`Uitgang "${U[Number(b.dataset.weg)].naam}" verwijderen?`, 'Verwijderen', true)) { U.splice(Number(b.dataset.weg), 1); teken(); }
      }
    };
    el.oninput = e => {
      const i = e.target; if (i.dataset.i === undefined) return;
      const u = U[Number(i.dataset.i)];
      u[i.dataset.k] = i.type === 'checkbox' ? i.checked : i.type === 'number' ? Number(i.value) : i.value;
      $('#uiOpslaan').disabled = !vuil();
    };
    el.onchange = e => { if (e.target.dataset.k === 'soort') teken(); };
  },
  state() { if (!vuil()) { U = null; if ($('#uiLijst')) teken(); } },
  live(L) {
    for (const [id, s] of Object.entries(L.s.uitgangen || {})) {
      const d = document.querySelector(`[data-dot="${id}"]`); if (d) d.className = 'dot' + (s.ok ? ' ok' : '');
      const t = document.querySelector(`[data-status="${id}"]`); if (t) t.textContent = (s.tekst || '') + (s.fps ? ` · ${s.fps} frames/s` : '');
    }
  },
};
