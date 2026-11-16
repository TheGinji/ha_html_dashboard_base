const CSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; " +
  "img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'";

// Kioskmodus: Home Assistant verbergt dan de zijbalk. Dat gaat met een event op window
// (hass-kiosk-mode); Home Assistant zet het daarna in hass.kioskMode. Bij een oudere
// Home Assistant luistert niemand naar het event en blijft hass.kioskMode leeg.
const KIOSK_EVENT = "hass-kiosk-mode";
const KIOSK_WAIT_MS = 1500;
const KIOSK_UNSUPPORTED =
  "Deze versie van Home Assistant kent geen kioskmodus. Werk Home Assistant bij.";

// Voorkeuren: een pagina in het afgeschermde iframe kan zelf niets onthouden. Het paneel bewaart
// daarom een klein JSON-object per dashboard en per apparaat, in de opslag van de browser (prefs).
// Wat voor alle apparaten moet gelden, bewaart Home Assistant zelf (sharedPrefs, vanaf 0.6.0).
const PREFS_MAX = 8000;
const PREFS_TOO_BIG = "Te veel gegevens: voorkeuren mogen samen maximaal 8 kB zijn.";
const PREFS_BAD = "prefs() verwacht een object, bijvoorbeeld { sleutel: waarde }.";
const SHARED_BAD = "sharedPrefs() verwacht een object, bijvoorbeeld { sleutel: waarde }.";

const BRIDGE = `(()=>{const w=new Map(),subs=new Set();let n=0;
addEventListener("message",e=>{if(e.source!==parent)return;const m=e.data;
if(!m||m.dbase!==1)return;
if(m.event){subs.forEach(cb=>{try{cb(m.payload)}catch(x){console.error(x)}});return}
const r=w.get(m.id);if(!r)return;w.delete(m.id);
m.ok?r.res(m.result):r.rej(new Error(m.error))});
const req=(op,args)=>new Promise((res,rej)=>{const id=++n;w.set(id,{res,rej});
parent.postMessage({dbase:1,id,op,args},"*")});
window.DashboardBase=Object.freeze({
registry:()=>req("registry"),states:()=>req("states"),info:()=>req("info"),
call:(domain,service,data={})=>req("call",{domain,service,data}),
history:(series,hours=24)=>req("history",{series,hours}),
forecast:(entity_id,type)=>req("forecast",{entity_id,type}),
kiosk:(on)=>req("kiosk",{on:on===undefined?null:!!on}),
prefs:(patch)=>req("prefs",{patch:patch===undefined?null:patch}),
sharedPrefs:(patch)=>req("shared_prefs",{patch:patch===undefined?null:patch}),
subscribe(cb){subs.add(cb);return()=>subs.delete(cb)}});})();`;

class DashboardBasePanel extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>
      :host{display:block;position:relative;height:100vh;height:100dvh;
        background:var(--primary-background-color)}
      iframe{position:absolute;inset:0;display:block;width:100%;height:100%;border:0}
      #msg{padding:24px;font-family:sans-serif;color:var(--primary-text-color)}
      #menu{position:fixed;top:8px;left:8px;z-index:2;width:40px;height:40px;
        border-radius:50%;border:0;opacity:.6}
    </style>
    <button id="menu" hidden aria-label="Menu">☰</button>
    <div id="msg" hidden></div>`;
    this._menu = root.getElementById("menu");
    this._msg = root.getElementById("msg");
    this._menu.addEventListener("click", () =>
      this.dispatchEvent(
        new Event("hass-toggle-menu", { bubbles: true, composed: true })
      )
    );
    this._onMessage = (e) => this._handle(e);
    this._onResize = () => this._fit();
    this._narrow = false;
    this._kioskWaiters = new Set();
    this._kioskOwned = false;
    this._kioskChain = Promise.resolve();
  }

  set hass(hass) {
    this._hass = hass;
    this._kioskWaiters.forEach((w) => w.check());
    this._showMenu();
    this._maybeStart();
  }

  // Elk dashboard heeft een eigen paneel. Het id van de instelling zit in de
  // paneelinstellingen; het paneel stuurt dat bij elke opdracht mee. Een pagina in het
  // iframe kan dat id niet zelf kiezen.
  set panel(panel) {
    this._entryId = panel && panel.config ? panel.config.entry_id : undefined;
    this._maybeStart();
  }

  set narrow(value) {
    this._narrow = !!value;
    this._showMenu();
  }

  // Het menuknopje is er alleen als Home Assistant zelf geen zijbalk toont (smal scherm).
  // In kioskmodus is het verborgen: dan wil je een schoon scherm.
  _showMenu() {
    this._menu.hidden = !this._narrow || this._kioskOn();
  }

  connectedCallback() {
    this._failed = false;
    window.addEventListener("message", this._onMessage);
    window.addEventListener("resize", this._onResize);
    requestAnimationFrame(() => this._fit());
    this._fitTimer = setTimeout(() => this._fit(), 400);
    this._maybeStart();
  }

  disconnectedCallback() {
    window.removeEventListener("message", this._onMessage);
    window.removeEventListener("resize", this._onResize);
    clearTimeout(this._fitTimer);
    this._stop();
  }

  // Het paneel begint soms onder een rand van Home Assistant zelf (bijvoorbeeld de
  // statusbalk van een telefoon). Dan is 100% van het scherm te hoog en valt de
  // onderkant buiten beeld. Daarom: schermhoogte min de plek waar het paneel begint.
  _fit() {
    const top = Math.max(0, this.getBoundingClientRect().top);
    this.style.height = `${Math.max(0, Math.round(window.innerHeight - top))}px`;
  }

  _maybeStart() {
    if (
      this._started ||
      this._failed ||
      !this._hass ||
      !this._entryId ||
      !this.isConnected
    )
      return;
    this._started = true;
    this._start().catch((err) => this._fail(err));
  }

  _stop() {
    this._started = false;
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
    this._kioskRelease();
  }

  _fail(err) {
    this._failed = true;
    this._frame?.remove();
    this._frame = null;
    this._stop();
    this._msg.hidden = false;
    this._msg.textContent = err?.message || "Dashboard Base: onbekende fout";
  }

  async _start() {
    const conn = this._hass.connection;
    this._kioskRestore();
    const unsub = await conn.subscribeMessage(
      (payload) => this._post({ dbase: 1, event: true, payload }),
      { type: "html_dashboard_base/subscribe", entry_id: this._entryId }
    );
    if (!this._started) {
      unsub();
      return;
    }
    this._unsub = unsub;
    const { html } = await conn.sendMessagePromise({
      type: "html_dashboard_base/get_html",
      entry_id: this._entryId,
    });
    this._show(html);
  }

  _show(html) {
    this._frame?.remove();
    const frame = document.createElement("iframe");
    frame.setAttribute("sandbox", "allow-scripts");
    let loads = 0;
    frame.addEventListener("load", () => {
      if (++loads > 1) {
        this._fail(new Error("Het dashboard is weggenavigeerd en is gestopt."));
      }
    });
    frame.srcdoc = this._wrap(html);
    this._frame = frame;
    this.shadowRoot.appendChild(frame);
  }

  _wrap(html) {
    const inject =
      `<meta http-equiv="Content-Security-Policy" content="${CSP}">` +
      `<script>${BRIDGE}</script>`;
    const head = /<head[^>]*>/i;
    return head.test(html)
      ? html.replace(head, (m) => m + inject)
      : `<!doctype html><html><head><meta charset="utf-8">${inject}</head>` +
          `<body>${html}</body></html>`;
  }

  async _handle(e) {
    if (!this._frame || e.source !== this._frame.contentWindow) return;
    const m = e.data;
    if (!m || m.dbase !== 1 || typeof m.id !== "number") return;
    try {
      const result = await this._op(m.op, m.args || {});
      this._post({ dbase: 1, id: m.id, ok: true, result });
    } catch (err) {
      this._post({ dbase: 1, id: m.id, ok: false, error: err?.message || "Fout" });
    }
  }

  _op(op, a) {
    const c = this._hass.connection;
    const entry_id = this._entryId;
    if (op === "registry")
      return c.sendMessagePromise({ type: "html_dashboard_base/registry", entry_id });
    if (op === "states")
      return c.sendMessagePromise({ type: "html_dashboard_base/states", entry_id });
    if (op === "info")
      return c.sendMessagePromise({ type: "html_dashboard_base/info" });
    if (op === "call")
      return c.sendMessagePromise({
        type: "html_dashboard_base/call",
        entry_id,
        domain: String(a.domain),
        service: String(a.service),
        data: a.data || {},
      });
    if (op === "history")
      return c.sendMessagePromise({
        type: "html_dashboard_base/history",
        entry_id,
        series: (Array.isArray(a.series) ? a.series : []).map((s) => ({
          entity_id: String(s && s.entity_id),
          ...(s && s.attribute ? { attribute: String(s.attribute) } : {}),
        })),
        hours: Math.round(Number(a.hours)) || 24,
      });
    if (op === "forecast")
      return c.sendMessagePromise({
        type: "html_dashboard_base/forecast",
        entry_id,
        entity_id: String(a.entity_id),
        ...(a.type ? { forecast_type: String(a.type) } : {}),
      });
    if (op === "kiosk") return this._kiosk(a.on);
    if (op === "prefs") return this._prefs(a.patch);
    if (op === "shared_prefs") return this._sharedPrefs(a.patch);
    return Promise.reject(new Error("Onbekende opdracht"));
  }

  // sharedPrefs() werkt als prefs(), maar het object staat in Home Assistant zelf en geldt dus op
  // elk apparaat. Het samenvoegen en de grens van 8 kB doet Home Assistant; hier alleen de vorm.
  _sharedPrefs(patch) {
    if (patch !== null && patch !== undefined && (typeof patch !== "object" || Array.isArray(patch)))
      return Promise.reject(new Error(SHARED_BAD));
    return this._hass.connection.sendMessagePromise({
      type: "html_dashboard_base/shared_prefs",
      entry_id: this._entryId,
      ...(patch ? { patch } : {}),
    });
  }

  // prefs() geeft de bewaarde voorkeuren terug. prefs({ a: 1, b: null }) voegt samen met wat er
  // staat: a wordt gezet, b wordt gewist. Het antwoord is het nieuwe object. Alleen JSON-waarden.
  _prefs(patch) {
    const key = `html_dashboard_base_prefs_${this._entryId}`;
    let cur = this._prefsMem;
    if (!cur) {
      try {
        const v = JSON.parse(localStorage.getItem(key) || "{}");
        cur = v && typeof v === "object" && !Array.isArray(v) ? v : {};
      } catch (_) {
        cur = {};
      }
    }
    if (patch === null || patch === undefined) return Promise.resolve(cur);
    if (typeof patch !== "object" || Array.isArray(patch))
      return Promise.reject(new Error(PREFS_BAD));
    const next = { ...cur };
    for (const [k, v] of Object.entries(patch)) {
      if (k === "__proto__") continue;
      if (v === null) delete next[k];
      else next[k] = v;
    }
    let text;
    try {
      text = JSON.stringify(next);
    } catch (_) {
      return Promise.reject(new Error(PREFS_BAD));
    }
    if (text.length > PREFS_MAX) return Promise.reject(new Error(PREFS_TOO_BIG));
    const clean = JSON.parse(text);
    try {
      localStorage.setItem(key, text);
      this._prefsMem = null;
    } catch (_) {
      // Opslag geblokkeerd of vol: dan onthoudt het paneel het tot het paneel sluit.
      this._prefsMem = clean;
    }
    return Promise.resolve(clean);
  }

  // kiosk() zonder argument geeft de stand, kiosk(true/false) zet de modus aan of uit.
  // De keuze wordt per apparaat onthouden en komt terug als dit paneel weer opent.
  // De opdrachten gaan een voor een, zodat snel aan en uit tikken netjes in volgorde loopt.
  _kiosk(on) {
    const run = async () => {
      if (typeof on !== "boolean") return { on: this._kioskOn() };
      await this._kioskSet(on);
      this._kioskRemember(on);
      return { on: this._kioskOn() };
    };
    const result = this._kioskChain.then(run);
    this._kioskChain = result.catch(() => {});
    return result;
  }

  _kioskOn() {
    return this._hass?.kioskMode === true;
  }

  // Zet de modus en wacht tot Home Assistant dat bevestigt via hass.kioskMode.
  _kioskSet(enable) {
    if (this._kioskOn() === enable) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const waiter = {
        check: () => {
          if (this._kioskOn() === enable) finish();
        },
      };
      const finish = (err) => {
        clearTimeout(timer);
        this._kioskWaiters.delete(waiter);
        if (err) reject(err);
        else resolve();
      };
      const timer = setTimeout(
        () => finish(new Error(KIOSK_UNSUPPORTED)),
        KIOSK_WAIT_MS
      );
      this._kioskWaiters.add(waiter);
      // Alleen een modus die wij zelf aanzetten, zetten wij ook weer los.
      this._kioskOwned = enable;
      window.dispatchEvent(new CustomEvent(KIOSK_EVENT, { detail: { enable } }));
    });
  }

  // Bij weggaan of een fout geven we de zijbalk terug, anders zit de gebruiker vast
  // zonder menu. De voorkeur blijft staan; bij terugkomen gaat de modus weer aan.
  _kioskRelease() {
    if (!this._kioskOwned) return;
    this._kioskOwned = false;
    window.dispatchEvent(
      new CustomEvent(KIOSK_EVENT, { detail: { enable: false } })
    );
  }

  _kioskKey() {
    return `html_dashboard_base_kiosk_${this._entryId}`;
  }

  _kioskRemember(on) {
    try {
      if (on) localStorage.setItem(this._kioskKey(), "1");
      else localStorage.removeItem(this._kioskKey());
    } catch (_) {
      /* opslag geblokkeerd: de modus werkt, alleen niet na heropenen */
    }
  }

  // Bij het openen: de onthouden voorkeur toepassen. ?dbase_kiosk=0 in het adres wist de
  // voorkeur, voor als een dashboard geen schakelaar heeft om de modus uit te zetten.
  _kioskRestore() {
    let want = false;
    try {
      const reset = new URLSearchParams(location.search).get("dbase_kiosk") === "0";
      if (reset) localStorage.removeItem(this._kioskKey());
      want = !reset && localStorage.getItem(this._kioskKey()) === "1";
    } catch (_) {
      return;
    }
    // In dezelfde rij als de opdrachten van de pagina: vraagt de pagina meteen de stand
    // op, dan krijgt ze het antwoord pas nadat de onthouden modus is toegepast.
    if (want)
      this._kioskChain = this._kioskChain
        .then(() => this._kioskSet(true))
        .catch(() => {});
  }

  _post(msg) {
    this._frame?.contentWindow?.postMessage(msg, "*");
  }
}

customElements.define("html-dashboard-base-panel", DashboardBasePanel);
