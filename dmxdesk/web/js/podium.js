// Podium: tekent alle lampen met hun echte kleur (live), en laat je lampen kiezen of verslepen.
import { K, clamp } from './kern.js';

const LASER = '#33ff77';

function rgb(hex) {
  const h = (hex || '#000000').slice(1);
  return [parseInt(h.slice(0, 2), 16) || 0, parseInt(h.slice(2, 4), 16) || 0, parseInt(h.slice(4, 6), 16) || 0];
}
function helderheid(hex) { const [r, g, b] = rgb(hex); return Math.max(r, g, b) / 255; }
function gloedKleur(hex, a) {
  // de kleur op volle sterkte met doorzichtigheid a (de helderheid van de lamp zit dan in a)
  const [r, g, b] = rgb(hex); const m = Math.max(r, g, b) || 1;
  return `rgba(${Math.round(r / m * 255)},${Math.round(g / m * 255)},${Math.round(b / m * 255)},${a})`;
}

export class Podium {
  constructor(el, opties = {}) {
    this.el = el;
    this.o = Object.assign({ modus: 'kijk', hoogte: '42vh', labels: true, geselecteerd: new Set() }, opties);
    this.sel = this.o.geselecteerd;
    el.classList.add('podium');
    el.style.height = this.o.hoogte;
    el.innerHTML = `<canvas></canvas><div class="podiumhint"></div><div class="podiumknoppen"></div>`;
    this.canvas = el.querySelector('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.hint = el.querySelector('.podiumhint');
    this.band = null; this.sleep = null;
    this.ro = new ResizeObserver(() => this.maat());
    this.ro.observe(el);
    this.maat();
    this.canvas.addEventListener('pointerdown', e => this.omlaag(e));
    this.canvas.addEventListener('pointermove', e => this.beweeg(e));
    this.canvas.addEventListener('pointerup', e => this.omhoog(e));
    this.canvas.addEventListener('pointercancel', e => this.omhoog(e));
    this.zetModus(this.o.modus);
  }

  zetModus(m) {
    this.o.modus = m;
    this.hint.textContent = m === 'kies' ? 'Klik om lampen te kiezen · Shift/Ctrl = erbij · sleep = rechthoek'
      : m === 'verplaats' ? 'Sleep lampen naar hun plek (links/rechts = volgorde van de effecten)' : '';
    this.canvas.style.cursor = m === 'kijk' ? 'default' : m === 'verplaats' ? 'grab' : 'pointer';
    this.teken();
  }

  weg() { this.ro.disconnect(); }

  maat() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (!w || !h) return;
    this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr);
    this.w = w; this.h = h; this.dpr = dpr;
    this.teken();
  }

  vlak() {
    const m = 30;
    return { x0: m, y0: m, bw: this.w - 2 * m, bh: this.h - 2 * m - 12 };
  }
  pos(f) {
    const v = this.vlak();
    return [v.x0 + f.x / 100 * v.bw, v.y0 + f.y / 100 * v.bh];
  }
  straal() { return clamp(Math.min(this.w, this.h * 1.6) / 55, 8, 17); }

  vormen() {
    // per lamp: plek en hoe groot, om te tekenen en om op te klikken
    const S = K.S; if (!S) return [];
    const r = this.straal(), v = this.vlak();
    return S.fixtures.map(f => {
      const p = S.profielen[f.profiel] || {};
      const [x, y] = this.pos(f);
      const soort = p.soort || 'par';
      const breed = soort === 'bar' ? Math.max(r * 2, (f.breedte || 10) / 100 * v.bw) : 0;
      return { f, x, y, soort, breed, r };
    });
  }

  raak(px, py) {
    const vormen = this.vormen();
    for (let i = vormen.length - 1; i >= 0; i--) {
      const s = vormen[i];
      if (s.soort === 'bar') {
        if (Math.abs(px - s.x) <= s.breed / 2 + 4 && Math.abs(py - s.y) <= s.r) return s.f;
      } else if (Math.hypot(px - s.x, py - s.y) <= s.r * 1.3) return s.f;
    }
    return null;
  }

  teken() {
    const ctx = this.ctx, S = K.S;
    if (!S || !this.w) return;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.w, this.h);
    const v = this.vlak();
    // podiumvloer
    ctx.strokeStyle = 'rgba(255,255,255,.06)'; ctx.lineWidth = 1;
    for (let i = 1; i < 10; i++) {
      const x = v.x0 + v.bw * i / 10; ctx.beginPath(); ctx.moveTo(x, v.y0); ctx.lineTo(x, v.y0 + v.bh); ctx.stroke();
    }
    for (let i = 1; i < 5; i++) {
      const y = v.y0 + v.bh * i / 5; ctx.beginPath(); ctx.moveTo(v.x0, y); ctx.lineTo(v.x0 + v.bw, y); ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(255,255,255,.12)'; ctx.strokeRect(v.x0, v.y0, v.bw, v.bh);
    ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.font = '600 10px system-ui'; ctx.textAlign = 'center';
    ctx.fillText('PUBLIEK', v.x0 + v.bw / 2, this.h - 8);

    const voorbeeld = {};
    for (const vb of (K.L.v || [])) voorbeeld[vb.id] = vb;
    const vormen = this.vormen();
    ctx.globalCompositeOperation = 'lighter';
    for (const s of vormen) this.gloed(s, voorbeeld[s.f.id]);
    ctx.globalCompositeOperation = 'source-over';
    for (const s of vormen) this.lamp(s, voorbeeld[s.f.id]);
    if (this.band) {
      const b = this.band;
      ctx.fillStyle = 'rgba(255,196,0,.08)'; ctx.strokeStyle = 'rgba(255,196,0,.7)';
      ctx.fillRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); ctx.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
    }
  }

  gloed(s, vb) {
    const ctx = this.ctx, { x, y, r } = s;
    if (!vb) return;
    if (s.soort === 'moving' && vb.p !== undefined) {
      const kleur = vb.c[0]; const hl = helderheid(kleur); if (hl < 0.03) return;
      const a = (vb.p - 0.5) * Math.PI * 1.5;
      const lengte = r * 2.5 + vb.t * r * 7;
      const dx = Math.sin(a), dy = Math.cos(a);
      const ex = x + dx * lengte, ey = y + dy * lengte, br = r * 0.5 + vb.t * r * 1.2;
      ctx.beginPath(); ctx.moveTo(x - dy * r * 0.3, y + dx * r * 0.3);
      ctx.lineTo(ex - dy * br, ey + dx * br); ctx.lineTo(ex + dy * br, ey - dx * br); ctx.lineTo(x + dy * r * 0.3, y - dx * r * 0.3);
      ctx.closePath();
      ctx.fillStyle = gloedKleur(kleur, 0.28 * hl); ctx.fill();
      const spot = ctx.createRadialGradient(ex, ey, 0, ex, ey, br * 1.3);
      spot.addColorStop(0, gloedKleur(kleur, 0.55 * hl));
      spot.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = spot; ctx.beginPath(); ctx.arc(ex, ey, br * 1.3, 0, Math.PI * 2); ctx.fill();
      return;
    }
    if (s.soort === 'rook' && vb.r !== undefined) {
      if (vb.r <= 0.01) return;
      const g = ctx.createRadialGradient(x, y - r, 0, x, y - r, r * 5);
      g.addColorStop(0, `rgba(200,210,230,${0.35 * vb.r})`); g.addColorStop(1, 'rgba(200,210,230,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y - r, r * 5, 0, Math.PI * 2); ctx.fill();
      return;
    }
    const cellen = vb.c || [];
    cellen.forEach((kleur, i) => {
      const hl = helderheid(kleur); if (hl < 0.03) return;
      let cx = x;
      if (s.soort === 'bar' && cellen.length > 1) cx = x - s.breed / 2 + (i + 0.5) * s.breed / cellen.length;
      const kl = s.soort === 'laser' && kleur.toLowerCase() === '#ffffff' ? LASER : kleur;
      const rg = s.soort === 'bar' ? Math.max(r * 1.4, s.breed / cellen.length) : r * 3.2;
      const g = ctx.createRadialGradient(cx, y, 0, cx, y, rg);
      g.addColorStop(0, gloedKleur(kl, 0.5 * hl));
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, y, rg, 0, Math.PI * 2); ctx.fill();
    });
  }

  lamp(s, vb) {
    const ctx = this.ctx, { f, x, y, r } = s;
    const gekozen = this.sel.has(f.id);
    const cellen = vb ? vb.c : ['#000000'];
    ctx.lineWidth = gekozen ? 2.5 : 1.2;
    ctx.strokeStyle = gekozen ? '#ffc400' : 'rgba(255,255,255,.35)';
    if (s.soort === 'bar') {
      const n = Math.max(1, cellen.length), bw = s.breed, h = r * 0.9;
      for (let i = 0; i < n; i++) {
        ctx.fillStyle = cellen[i] || '#000';
        ctx.fillRect(x - bw / 2 + i * bw / n, y - h / 2, bw / n, h);
      }
      ctx.strokeRect(x - bw / 2, y - h / 2, bw, h);
    } else if (s.soort === 'laser') {
      const kl = cellen[0] && cellen[0].toLowerCase() === '#ffffff' ? LASER : cellen[0];
      ctx.fillStyle = helderheid(cellen[0]) > 0.03 ? kl : '#111';
      ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else if (s.soort === 'rook') {
      const niveau = vb && vb.r !== undefined ? vb.r : 0;
      ctx.fillStyle = `rgba(${90 + 120 * niveau},${95 + 120 * niveau},${110 + 120 * niveau},1)`;
      ctx.beginPath(); ctx.roundRect(x - r, y - r * 0.7, r * 2, r * 1.4, 4); ctx.fill(); ctx.stroke();
    } else if (s.soort === 'moving') {
      ctx.fillStyle = '#1b1b20';
      ctx.beginPath(); ctx.roundRect(x - r, y - r, r * 2, r * 2, r * 0.5); ctx.fill(); ctx.stroke();
      ctx.fillStyle = cellen[0] || '#000'; ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.fillStyle = cellen[0] || '#000';
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    if (this.o.labels) {
      ctx.fillStyle = gekozen ? '#ffc400' : 'rgba(255,255,255,.55)';
      ctx.font = `${gekozen ? 700 : 500} 11px system-ui`; ctx.textAlign = 'center';
      ctx.fillText(f.naam, x, y + (s.soort === 'bar' ? r * 0.5 : r) + 13);
    }
  }

  // -------------------------------------------------------------- muis en vinger
  punt(e) { const b = this.canvas.getBoundingClientRect(); return [e.clientX - b.left, e.clientY - b.top]; }

  omlaag(e) {
    if (this.o.modus === 'kijk') return;
    const [px, py] = this.punt(e);
    const f = this.raak(px, py);
    this.canvas.setPointerCapture(e.pointerId);
    const erbij = e.shiftKey || e.ctrlKey || e.metaKey;
    if (this.o.modus === 'verplaats') {
      if (f) { this.sleep = { f, dx: 0, dy: 0 }; this.canvas.style.cursor = 'grabbing'; if (!erbij) this.sel.clear(); this.sel.add(f.id); this.selectieGewijzigd(); }
      return;
    }
    if (f) {
      if (erbij) { this.sel.has(f.id) ? this.sel.delete(f.id) : this.sel.add(f.id); }
      else if (this.sel.size === 1 && this.sel.has(f.id)) this.sel.clear();
      else { this.sel.clear(); this.sel.add(f.id); }
      this.selectieGewijzigd();
    } else {
      if (!erbij) { this.sel.clear(); this.selectieGewijzigd(); }
      this.band = { x0: px, y0: py, x1: px, y1: py, sx: px, sy: py };
    }
  }

  beweeg(e) {
    const [px, py] = this.punt(e);
    if (this.sleep) {
      const v = this.vlak();
      this.sleep.f.x = Math.round(clamp((px - v.x0) / v.bw * 100, 0, 100) * 2) / 2;
      this.sleep.f.y = Math.round(clamp((py - v.y0) / v.bh * 100, 0, 100) * 2) / 2;
      this.sleep.bewogen = true;
      this.teken();
    } else if (this.band) {
      const b = this.band;
      b.x0 = Math.min(b.sx, px); b.x1 = Math.max(b.sx, px); b.y0 = Math.min(b.sy, py); b.y1 = Math.max(b.sy, py);
      this.teken();
    } else if (this.o.modus !== 'kijk') {
      this.canvas.style.cursor = this.raak(px, py) ? (this.o.modus === 'verplaats' ? 'grab' : 'pointer') : 'default';
    }
  }

  omhoog() {
    if (this.sleep) {
      const s = this.sleep; this.sleep = null;
      this.canvas.style.cursor = 'grab';
      if (s.bewogen && this.o.bijVerplaats) this.o.bijVerplaats(s.f);
    }
    if (this.band) {
      const b = this.band; this.band = null;
      if (b.x1 - b.x0 > 4 || b.y1 - b.y0 > 4) {
        for (const s of this.vormen()) if (s.x >= b.x0 && s.x <= b.x1 && s.y >= b.y0 && s.y <= b.y1) this.sel.add(s.f.id);
        this.selectieGewijzigd();
      }
      this.teken();
    }
  }

  selectieGewijzigd() { this.teken(); if (this.o.bijSelectie) this.o.bijSelectie(this.sel); }
}
