const CSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; " +
  "img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'";

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
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeStart();
  }

  set narrow(value) {
    this._menu.hidden = !value;
  }

  connectedCallback() {
    this._failed = false;
    window.addEventListener("message", this._onMessage);
    this._maybeStart();
  }

  disconnectedCallback() {
    window.removeEventListener("message", this._onMessage);
    this._stop();
  }

  _maybeStart() {
    if (this._started || this._failed || !this._hass || !this.isConnected) return;
    this._started = true;
    this._start().catch((err) => this._fail(err));
  }

  _stop() {
    this._started = false;
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
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
    const unsub = await conn.subscribeMessage(
      (payload) => this._post({ dbase: 1, event: true, payload }),
      { type: "html_dashboard_base/subscribe" }
    );
    if (!this._started) {
      unsub();
      return;
    }
    this._unsub = unsub;
    const { html } = await conn.sendMessagePromise({
      type: "html_dashboard_base/get_html",
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
    if (op === "registry")
      return c.sendMessagePromise({ type: "html_dashboard_base/registry" });
    if (op === "states")
      return c.sendMessagePromise({ type: "html_dashboard_base/states" });
    if (op === "info")
      return c.sendMessagePromise({ type: "html_dashboard_base/info" });
    if (op === "call")
      return c.sendMessagePromise({
        type: "html_dashboard_base/call",
        domain: String(a.domain),
        service: String(a.service),
        data: a.data || {},
      });
    return Promise.reject(new Error("Onbekende opdracht"));
  }

  _post(msg) {
    this._frame?.contentWindow?.postMessage(msg, "*");
  }
}

customElements.define("html-dashboard-base-panel", DashboardBasePanel);
