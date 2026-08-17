/**
 * opcom-pzu-card — grafic al preturilor PZU la 15 minute.
 *
 * Face parte din integrarea OPCOM PZU si este inregistrat automat de aceasta,
 * deci nu trebuie adaugat manual ca resursa de frontend.
 *
 * Fara dependinte externe: tot graficul e SVG generat local.
 *
 * Configurare minima:
 *   type: custom:opcom-pzu-card
 *
 * Optiuni:
 *   entity   senzorul de pret (implicit: se detecteaza singur)
 *   title    titlul cardului
 *   span     "48h" (implicit) sau "today"
 *   height   inaltimea graficului in pixeli (implicit 200)
 */

const VERSION = "1.0.1";

// rampa albastra secventiala: pret mic -> pret mare
const RAMP = [
  [0.0, "#86b6ef"],
  [0.45, "#5598e7"],
  [0.75, "#2a78d6"],
  [1.0, "#1c5cab"],
];
const WINDOW_COLOR = "#0ca30c";

const NBSP = " ";

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const fmtPrice = (v) => (v == null ? "–" : Math.round(v).toLocaleString("ro-RO"));
const fmtHour = (d) =>
  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

const hexToRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const toHex = (n) => Math.round(clamp(n, 0, 255)).toString(16).padStart(2, "0");

/** Interpoleaza rampa albastra: 0 = cel mai ieftin interval, 1 = cel mai scump. */
function rampColor(t) {
  const x = clamp(t, 0, 1);
  for (let i = 1; i < RAMP.length; i++) {
    const [p0, c0] = RAMP[i - 1];
    const [p1, c1] = RAMP[i];
    if (x <= p1) {
      const f = p1 === p0 ? 0 : (x - p0) / (p1 - p0);
      const a = hexToRgb(c0);
      const b = hexToRgb(c1);
      return "#" + a.map((v, k) => toHex(v + (b[k] - v) * f)).join("");
    }
  }
  return RAMP[RAMP.length - 1][1];
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

class OpcomPzuCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._rows = [];
    this._resize = null;
    this._width = 0;
  }

  // -- ciclul de viata al cardului -----------------------------------------
  setConfig(config) {
    this._config = { span: "48h", height: 200, ...(config || {}) };
    this._built = false;
  }

  static getStubConfig() {
    return { type: "custom:opcom-pzu-card" };
  }

  getCardSize() {
    return 6;
  }

  connectedCallback() {
    this._resize = new ResizeObserver(() => {
      const w = this.clientWidth;
      if (w && Math.abs(w - this._width) > 4) {
        this._width = w;
        this._render();
      }
    });
    this._resize.observe(this);
  }

  disconnectedCallback() {
    if (this._resize) this._resize.disconnect();
    this._resize = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // -- date ----------------------------------------------------------------
  _findEntity() {
    if (this._config.entity) return this._config.entity;
    const states = this._hass?.states || {};
    for (const id of Object.keys(states)) {
      if (id.startsWith("sensor.") && Array.isArray(states[id].attributes?.raw_today)) {
        return id;
      }
    }
    return null;
  }

  _collect() {
    const id = this._findEntity();
    const st = id ? this._hass.states[id] : null;
    if (!st) return { error: "Nu am gasit senzorul de pret OPCOM." };

    const a = st.attributes || {};
    const today = a.raw_today || [];
    const tomorrow = this._config.span === "today" ? [] : a.raw_tomorrow || [];
    const rows = today.concat(tomorrow).map((s) => ({
      t: new Date(s.start).getTime(),
      v: s.value,
      hour: s.hour,
    }));
    if (!rows.length) return { error: "Nu am inca datele de la OPCOM." };

    return {
      entityId: id,
      rows,
      threshold: typeof a.threshold === "number" ? a.threshold : null,
      window: a.window || null,
      current: st.state === "unknown" || st.state === "unavailable" ? null : Number(st.state),
      currentHour: a.current_hour || null,
      rank: a.current_rank_today || null,
      slots: a.today?.slots || today.length,
      todayStats: a.today || null,
      tomorrowValid: !!a.tomorrow_valid,
      unit: a.unit_of_measurement || "Lei/MWh",
    };
  }

  // -- randare -------------------------------------------------------------
  _build() {
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      ha-card { padding: 12px 12px 6px; position: relative; overflow: hidden; }
      .head { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
              margin: 2px 4px 10px; }
      .head h2 { margin: 0; font-size: 16px; font-weight: 500;
                 color: var(--primary-text-color); }
      .kv { font-size: 13px; color: var(--secondary-text-color); }
      .kv b { color: var(--primary-text-color); font-weight: 600;
              font-variant-numeric: tabular-nums; }
      .msg { padding: 20px 4px; color: var(--secondary-text-color); font-size: 14px; }
      svg { display: block; width: 100%; overflow: visible; }
      .legend { display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 4px 4px;
                font-size: 12px; color: var(--secondary-text-color); }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
      .swatch.dash { height: 0; width: 14px; border-radius: 0;
                     border-top: 2px dashed var(--secondary-text-color); }
      .swatch.line { height: 3px; width: 14px; border-radius: 2px; }
      .tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
             transition: opacity .08s linear; background: var(--card-background-color,#fff);
             color: var(--primary-text-color); border: 1px solid var(--divider-color);
             border-radius: 6px; padding: 5px 8px; font-size: 12px; white-space: nowrap;
             box-shadow: 0 2px 8px rgba(0,0,0,.18); font-variant-numeric: tabular-nums; }
      .tip.on { opacity: 1; }
      rect.bar:hover { filter: brightness(1.25); }
    `;
    const card = document.createElement("ha-card");
    card.innerHTML = `<div class="head"></div><div class="body"></div>
                      <div class="legend"></div><div class="tip"></div>`;
    this.shadowRoot.replaceChildren(style, card);
    this._els = {
      card,
      head: card.querySelector(".head"),
      body: card.querySelector(".body"),
      legend: card.querySelector(".legend"),
      tip: card.querySelector(".tip"),
    };
    this._built = true;
  }

  _render() {
    if (!this._hass) return;
    if (!this._built) this._build();

    const d = this._collect();
    const { head, body, legend, tip } = this._els;

    if (d.error) {
      head.innerHTML = `<h2>${esc(this._config.title || "Pret PZU la 15 minute")}</h2>`;
      body.innerHTML = `<div class="msg">${esc(d.error)}</div>`;
      legend.innerHTML = "";
      return;
    }

    // ---- antet
    const win = d.window;
    head.innerHTML =
      `<h2>${esc(this._config.title || "Pret PZU la 15 minute")}</h2>` +
      `<span class="kv">acum <b>${fmtPrice(d.current)}</b> ${esc(d.unit)}</span>` +
      (d.rank ? `<span class="kv">locul <b>${d.rank}</b> din ${d.slots}</span>` : "") +
      (win ? `<span class="kv">fereastra <b>${esc(win.label)}</b></span>` : "");

    // ---- geometrie
    const W = Math.max(this.clientWidth || 400, 260);
    const H = Number(this._config.height) || 200;
    const padL = 40, padR = 6, padT = 10, padB = 20;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const rows = d.rows;
    const n = rows.length;
    const vMax = Math.max(...rows.map((r) => r.v), d.threshold ?? 0);
    // barele pornesc de la zero — altfel diferentele par mai mari decat sunt
    const yTop = Math.ceil((vMax * 1.08) / 100) * 100;
    const y = (v) => padT + plotH - (v / yTop) * plotH;
    const bw = plotW / n;

    const now = Date.now();
    const t0 = rows[0].t;
    const step = n > 1 ? rows[1].t - rows[0].t : 900000;
    const xOf = (t) => padL + ((t - t0) / (step * n)) * plotW;

    const vMin = Math.min(...rows.map((r) => r.v));
    const spread = Math.max(vMax - vMin, 1);

    // ---- bare
    let bars = "";
    rows.forEach((r, i) => {
      const x = padL + i * bw;
      const top = y(r.v);
      const h = Math.max(padT + plotH - top, 1);
      const c = rampColor((r.v - vMin) / spread);
      bars +=
        `<rect class="bar" x="${x.toFixed(2)}" y="${top.toFixed(2)}" ` +
        `width="${Math.max(bw - 0.6, 0.6).toFixed(2)}" height="${h.toFixed(2)}" ` +
        `fill="${c}" data-i="${i}" rx="1"/>`;
    });

    // ---- fereastra optima
    let winShape = "";
    if (win) {
      const a = new Date(win.start).getTime();
      const b = new Date(win.end).getTime();
      const x1 = clamp(xOf(a), padL, padL + plotW);
      const x2 = clamp(xOf(b), padL, padL + plotW);
      if (x2 > x1) {
        const yAvg = y(win.avg);
        winShape =
          `<rect x="${x1.toFixed(2)}" y="${padT}" width="${(x2 - x1).toFixed(2)}" ` +
          `height="${plotH}" fill="${WINDOW_COLOR}" opacity="0.10"/>` +
          `<line x1="${x1.toFixed(2)}" y1="${yAvg.toFixed(2)}" x2="${x2.toFixed(2)}" ` +
          `y2="${yAvg.toFixed(2)}" stroke="${WINDOW_COLOR}" stroke-width="3" ` +
          `stroke-linecap="round"/>`;
      }
    }

    // ---- prag
    let thrShape = "";
    if (d.threshold != null && d.threshold > 0 && d.threshold <= yTop) {
      const yt = y(d.threshold);
      thrShape =
        `<line x1="${padL}" y1="${yt.toFixed(2)}" x2="${(padL + plotW).toFixed(2)}" ` +
        `y2="${yt.toFixed(2)}" stroke="var(--secondary-text-color)" stroke-width="1.5" ` +
        `stroke-dasharray="5 4" opacity="0.85"/>`;
    }

    // ---- linia "acum"
    let nowShape = "";
    if (now >= t0 && now <= t0 + step * n) {
      const xn = xOf(now);
      nowShape =
        `<line x1="${xn.toFixed(2)}" y1="${padT - 4}" x2="${xn.toFixed(2)}" ` +
        `y2="${(padT + plotH).toFixed(2)}" stroke="var(--primary-text-color)" ` +
        `stroke-width="1.5" opacity="0.55"/>`;
    }

    // ---- axe
    let grid = "";
    const ticks = 4;
    for (let i = 0; i <= ticks; i++) {
      const v = (yTop / ticks) * i;
      const yy = y(v);
      grid +=
        `<line x1="${padL}" y1="${yy.toFixed(2)}" x2="${(padL + plotW).toFixed(2)}" ` +
        `y2="${yy.toFixed(2)}" stroke="var(--divider-color)" stroke-width="1" ` +
        `opacity="${i === 0 ? 0.9 : 0.45}"/>` +
        `<text x="${padL - 6}" y="${(yy + 3.5).toFixed(2)}" text-anchor="end" ` +
        `font-size="10" fill="var(--secondary-text-color)">${fmtPrice(v)}</text>`;
    }

    let xLabels = "";
    rows.forEach((r, i) => {
      const dt = new Date(r.t);
      if (dt.getMinutes() !== 0 || dt.getHours() % 6 !== 0) return;
      const x = padL + i * bw;
      const midnight = dt.getHours() === 0;
      if (midnight && i > 0) {
        xLabels +=
          `<line x1="${x.toFixed(2)}" y1="${padT}" x2="${x.toFixed(2)}" ` +
          `y2="${(padT + plotH).toFixed(2)}" stroke="var(--divider-color)" stroke-width="1"/>`;
      }
      xLabels +=
        `<text x="${x.toFixed(2)}" y="${(padT + plotH + 14).toFixed(2)}" ` +
        `text-anchor="middle" font-size="10" fill="var(--secondary-text-color)" ` +
        `${midnight ? 'font-weight="600"' : ""}>${fmtHour(dt)}</text>`;
    });

    body.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" ` +
      `preserveAspectRatio="xMidYMid meet" role="img" ` +
      `aria-label="Preturi PZU la 15 minute">` +
      grid + xLabels + winShape + bars + thrShape + nowShape +
      `</svg>`;

    // ---- legenda
    legend.innerHTML =
      `<span><i class="swatch" style="background:${RAMP[1][1]}"></i>Pret PZU (mai inchis = mai scump)</span>` +
      (win
        ? `<span><i class="swatch line" style="background:${WINDOW_COLOR}"></i>Fereastra optima${NBSP}${esc(
            win.label
          )}</span>`
        : "") +
      (d.threshold != null
        ? `<span><i class="swatch dash"></i>Prag ${fmtPrice(
            d.threshold
          )}</span>`
        : "") +
      (!d.tomorrowValid && this._config.span !== "today"
        ? `<span>Preturile de maine apar dupa 13:00–14:00</span>`
        : "");

    // ---- tooltip
    const svg = body.querySelector("svg");
    svg.addEventListener("mousemove", (ev) => {
      const target = ev.target;
      if (!(target instanceof SVGRectElement) || !target.classList.contains("bar")) {
        tip.classList.remove("on");
        return;
      }
      const i = Number(target.dataset.i);
      const r = rows[i];
      const dt = new Date(r.t);
      const day = dt.toLocaleDateString("ro-RO", { weekday: "short", day: "numeric", month: "short" });
      tip.innerHTML = `<b>${fmtPrice(r.v)}</b> ${esc(d.unit)}<br>${esc(day)} ${fmtHour(dt)}`;
      const box = this._els.card.getBoundingClientRect();
      tip.classList.add("on");
      const tw = tip.offsetWidth;
      tip.style.left = `${clamp(ev.clientX - box.left - tw / 2, 4, box.width - tw - 4)}px`;
      tip.style.top = `${ev.clientY - box.top - tip.offsetHeight - 12}px`;
    });
    svg.addEventListener("mouseleave", () => tip.classList.remove("on"));
  }
}

if (!customElements.get("opcom-pzu-card")) {
  customElements.define("opcom-pzu-card", OpcomPzuCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "opcom-pzu-card")) {
  window.customCards.push({
    type: "opcom-pzu-card",
    name: "OPCOM PZU",
    preview: true,
    description: "Preturi PZU la 15 minute, cu fereastra optima de injectie in retea.",
    documentationURL: "https://github.com/chindrisadrian/opcom",
  });
}

console.info(
  `%c OPCOM-PZU-CARD %c ${VERSION} `,
  "color:#fff;background:#2a78d6;font-weight:700",
  "color:#2a78d6;background:#e8f0fb"
);
