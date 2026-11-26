/* Remo IR Local panel — vanilla web component for Home Assistant (admin only). */

const API = "remo_ir_local";
const SLUG_RE = /^[a-z0-9_]{1,40}$/;
const STATUS = { ok: "正常", not_found: "未検出", fixed: "IP固定", unknown: "未確認" };

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtSig = (s) => `${esc(s.freq)}kHz / 要素数 ${esc(s.length)} / format ${esc(s.format)}`;

const CSS = `
:host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--paper-font-body1_-_font-family, Roboto, "Noto Sans JP", sans-serif); font-size:14px; }
header { display:flex; align-items:center; gap:8px; height:56px; padding:0 12px;
  background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff); }
h1 { margin:0; font-size:20px; font-weight:400; }
main { max-width:860px; margin:0 auto; padding:4px 16px 64px; }
section { padding:22px 0; border-bottom:1px solid var(--divider-color); }
section:last-child { border-bottom:0; }
h2 { margin:0 0 12px; font-size:16px; font-weight:500; }
h3 { margin:0 0 12px; font-size:18px; font-weight:500; }
p { margin:0 0 10px; line-height:1.6; }
label { display:block; margin:14px 0 4px; font-size:13px; color:var(--secondary-text-color); }
.hint, .state, .sub { color:var(--secondary-text-color); font-size:13px; }
.warn { color:var(--warning-color, #b26a00); }
.err { color:var(--error-color); min-height:18px; font-size:13px; }
.empty { color:var(--secondary-text-color); }
button { font:inherit; min-height:36px; padding:6px 14px; border-radius:8px; cursor:pointer;
  border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
button.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:transparent; }
button.danger { color:var(--error-color); }
button:disabled { opacity:.5; cursor:default; }
:host(.working) button { pointer-events:none; opacity:.6; }
:focus-visible { outline:2px solid var(--primary-color); outline-offset:2px; }
input, select { font:inherit; box-sizing:border-box; width:100%; min-height:36px; padding:6px 10px; border-radius:8px;
  border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
input.invalid { border-color:var(--error-color); }
.row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.row select { flex:1 1 220px; width:auto; }
.idrow { display:flex; }
.prefix { display:flex; align-items:center; padding:0 10px; white-space:nowrap; font-family:monospace; color:var(--secondary-text-color);
  background:var(--secondary-background-color); border:1px solid var(--divider-color); border-right:0; border-radius:8px 0 0 8px; }
.idrow input { border-radius:0 8px 8px 0; font-family:monospace; }
.facts { display:flex; flex-wrap:wrap; gap:6px 18px; margin:14px 0 10px; font-variant-numeric:tabular-nums; }
.banner { padding:10px 12px; border-radius:8px; margin:10px 0; background:var(--secondary-background-color); line-height:1.6; }
.banner.warn { border-left:4px solid var(--warning-color, #b26a00); }
.banner.ok { border-left:4px solid var(--success-color, #2e7d32); }
.list { list-style:none; margin:0; padding:0; }
.list li { display:flex; align-items:center; gap:12px; padding:10px 0; border-top:1px solid var(--divider-color); }
.list li:first-child { border-top:0; }
.list ha-icon { flex:none; color:var(--secondary-text-color); }
.list .main { flex:1; min-width:0; }
.list .name { font-weight:500; overflow-wrap:anywhere; }
.meta { display:flex; flex-wrap:wrap; gap:2px 14px; }
.actions { display:flex; flex:none; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
.chip { margin:0 6px 6px 0; }
#msg { position:sticky; top:0; z-index:5; }
.toast { padding:10px 16px; white-space:pre-line; line-height:1.5; background:var(--primary-text-color); color:var(--primary-background-color); }
.toast.error { background:var(--error-color); color:#fff; }
.toast.warn { background:var(--warning-color, #b26a00); color:#fff; }
.backdrop { position:fixed; inset:0; z-index:10; display:flex; align-items:center; justify-content:center; padding:16px; background:rgba(0,0,0,.5); }
.dialog { width:min(480px,100%); max-height:90vh; overflow:auto; padding:20px; border-radius:12px;
  background:var(--card-background-color); color:var(--primary-text-color); }
.dialog .actions { margin-top:20px; justify-content:flex-end; }
.dialog .actions .left { margin-right:auto; }
.refs { margin:8px 0; padding-left:18px; font-size:13px; overflow-wrap:anywhere; }
ol.steps { margin:0 0 8px; padding-left:22px; line-height:1.8; }
.note { margin:0 0 12px; font-size:13px; line-height:1.6; color:var(--secondary-text-color); }
.idlabel { padding:4px 0; font-family:monospace; font-size:15px; }
details { margin-top:16px; padding:0 12px; border:1px solid var(--divider-color); border-radius:8px; }
summary { padding:10px 0; font-weight:500; cursor:pointer; }
details[open] > summary { margin-bottom:2px; }
.explain { margin:12px 0 10px; font-size:13px; line-height:1.6; color:var(--secondary-text-color); }
.explain dt { margin-top:8px; font-weight:500; color:var(--primary-text-color); }
.explain dd { margin:2px 0 0; }
.chip[aria-pressed="true"] { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:transparent; }
@media (max-width:560px) { .list li { flex-wrap:wrap; } .actions { width:100%; justify-content:flex-start; } }
.pick { margin-top:16px; }
`;

class RemoIrLocalPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.s = { remos: [], sel: "", cap: null, regIcon: "", regArea: "", buttons: [], buttonsErr: "", modal: null };
    this._pickers = new Set();
    this._ready = false;
    this._working = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._pickers.forEach((p) => { p.hass = hass; });
    if (this._menu) this._menu.hass = hass;
    if (!this._ready) {
      this._ready = true;
      this._init();
    }
  }

  set narrow(v) {
    this._narrow = v;
    if (this._menu) this._menu.narrow = v;
  }

  // ------------------------------------------------------------------ setup

  _init() {
    const root = this.shadowRoot;
    root.innerHTML = `<style>${CSS}</style>
      <header><span id="menuSlot"></span><h1>Remo IR Local</h1></header>
      <div id="msg" role="status" aria-live="polite"></div>
      <main><section id="secRemo"></section><section id="secCapture"></section><section id="secList"></section></main>
      <div id="modal"></div>`;
    if (customElements.get("ha-menu-button")) {
      const m = document.createElement("ha-menu-button");
      m.hass = this._hass;
      m.narrow = this._narrow;
      root.getElementById("menuSlot").appendChild(m);
      this._menu = m;
    }
    root.addEventListener("click", (e) => this._onClick(e));
    root.addEventListener("change", (e) => this._onChange(e));
    root.addEventListener("input", (e) => this._onInput(e));
    root.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.s.modal) this._closeModal();
    });
    this._renderRemo();
    this._renderCapture();
    this._renderList();
    this._work(async () => {
      await this._loadRemos();
      await this._loadButtons();
    });
  }

  async _api(method, path, body) {
    try {
      return await this._hass.callApi(method, `${API}/${path}`, body);
    } catch (e) {
      const b = e && e.body && typeof e.body === "object" ? e.body : {};
      const err = new Error(b.error || b.message || (e && (e.error || e.message)) || "通信に失敗しました");
      err.body = b;
      err.status = e && e.status_code;
      throw err;
    }
  }

  async _work(fn) {
    if (this._working) return;
    this._working = true;
    this.classList.add("working");
    try {
      await fn();
    } catch (e) {
      this._toast(e.message || String(e), "error");
    } finally {
      this._working = false;
      this.classList.remove("working");
    }
  }

  _toast(text, kind = "info") {
    const el = this.shadowRoot.getElementById("msg");
    el.innerHTML = `<div class="toast ${kind}">${esc(text)}</div>`;
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { el.innerHTML = ""; }, kind === "info" ? 6000 : 14000);
  }

  _q(id) {
    const el = this.shadowRoot.getElementById(id);
    return el ? el.value.trim() : "";
  }

  // ---------------------------------------------------------------- loading

  async _loadRemos() {
    const r = await this._api("GET", "remos");
    this.s.remos = r.remos;
    if (!this.s.remos.some((x) => x.id === this.s.sel)) this.s.sel = this.s.remos[0]?.id || "";
    this._renderRemo();
    this._renderCapture();
  }

  async _loadButtons() {
    try {
      const r = await this._api("GET", "buttons");
      this.s.buttons = r.buttons;
      this.s.buttonsErr = "";
    } catch (e) {
      this.s.buttons = [];
      this.s.buttonsErr = e.message;
    }
    this._renderList();
  }

  // -------------------------------------------------------------- rendering

  _sec(id, html) {
    this.shadowRoot.getElementById(id).innerHTML = html;
  }

  _iconField(slot, value, onChange) {
    this._pickers.forEach((p) => { if (!p.isConnected) this._pickers.delete(p); });
    slot.textContent = "";
    let el;
    const label = "アイコン(任意)";
    if (customElements.get("ha-selector")) {
      el = document.createElement("ha-selector");
      el.hass = this._hass;
      el.selector = { icon: {} };
      el.value = value || "";
      el.label = label;
      el.required = false;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else if (customElements.get("ha-icon-picker")) {
      el = document.createElement("ha-icon-picker");
      el.hass = this._hass;
      el.value = value || "";
      el.label = label;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else {
      // フォールバック: テキスト入力
      slot.innerHTML = `<label for="iconText">${label}</label><input id="iconText" placeholder="mdi:television" autocomplete="off" spellcheck="false">`;
      el = slot.querySelector("input");
      el.value = value || "";
      el.addEventListener("input", () => onChange(el.value.trim()));
      return;
    }
    this._pickers.add(el);
    slot.appendChild(el);
  }

  _areaField(slot, value, onChange) {
    this._pickers.forEach((p) => { if (!p.isConnected) this._pickers.delete(p); });
    slot.textContent = "";
    let el;
    const label = "エリア(任意)";
    if (customElements.get("ha-selector")) {
      el = document.createElement("ha-selector");
      el.hass = this._hass;
      el.selector = { area: {} };
      el.value = value || "";
      el.label = label;
      el.required = false;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else if (customElements.get("ha-area-picker")) {
      el = document.createElement("ha-area-picker");
      el.hass = this._hass;
      el.value = value || "";
      el.label = label;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else {
      // フォールバック: HAのエリア一覧から選ぶ
      const areas = Object.values((this._hass && this._hass.areas) || {})
        .sort((a, b) => String(a.name).localeCompare(String(b.name), "ja"));
      slot.innerHTML = `<label for="areaSel">${label}</label><select id="areaSel"><option value="">(指定なし)</option>` +
        areas.map((a) => `<option value="${esc(a.area_id)}">${esc(a.name)}</option>`).join("") + `</select>`;
      el = slot.querySelector("select");
      el.value = value || "";
      el.addEventListener("change", () => onChange(el.value));
      return;
    }
    this._pickers.add(el);
    slot.appendChild(el);
  }

  _renderRemo() {
    const { remos, sel } = this.s;
    if (!remos.length) {
      this._sec("secRemo", `<h2>Remo</h2><p class="empty">Remoが未登録です。</p>
        <div class="row"><button class="primary" data-act="addRemo">Remoを追加</button></div>`);
      return;
    }
    const cur = remos.find((r) => r.id === sel);
    const opts = remos
      .map((r) => `<option value="${esc(r.id)}"${r.id === sel ? " selected" : ""}>${esc(r.name)} (${esc(r.id)})</option>`)
      .join("");
    const seen = cur && cur.last_seen ? `、最終確認 ${esc(new Date(cur.last_seen).toLocaleString("ja-JP"))}` : "";
    const state = cur
      ? `<p class="state${cur.status === "not_found" ? " warn" : ""}">IP ${esc(cur.ip || "未特定")}、${STATUS[cur.status] || "未確認"}${seen}</p>`
      : "";
    this._sec("secRemo", `<h2>Remo</h2>
      <div class="row"><select id="remoSel" aria-label="Remo">${opts}</select>
        <button data-act="refresh" title="ARPを走査して全RemoのIPを更新します">再読込</button>
        <button data-act="editRemo">設定</button><button data-act="addRemo">追加</button></div>${state}`);
  }

  _renderCapture() {
    const { remos, cap } = this.s;
    if (!remos.length) { this._sec("secCapture", ""); return; }
    let html = `<h2>信号を取得</h2>
      <ol class="steps"><li>Remoに向けて登録するリモコンの信号を送信してください。（信号を認識すると、青く光ります。）</li>
        <li>1の作業後すぐに、以下の「取得する」ボタンを押してください。</li></ol>
      <p class="note">※Remoは直近の1件しか赤外線信号を保持しません。複数登録する場合であっても1、2の順で実施してください。</p>
      <div class="row"><button class="primary" data-act="capture">取得する</button></div>`;
    if (cap) {
      html += `<div class="facts"><span>周波数 ${esc(cap.summary.freq)}kHz</span><span>要素数 ${esc(cap.summary.length)}</span><span>format ${esc(cap.summary.format)}</span></div>
        <div class="row"><button data-act="testSendCap">テスト送信</button></div>`;
      if (cap.same_as_previous) {
        html += `<div class="banner warn">前回取得した信号と完全に同じです。新しい信号を受信していない可能性があります。リモコンを押し直してから取得してください。</div>`;
      }
      if (cap.match) {
        html += `<div class="banner ok">この信号は <b>${esc(cap.match.entity_id)}</b>(${esc(cap.match.alias)})として登録済みです。追加の登録は不要です。</div>`;
      } else {
        html += `<div class="banner" style="margin-top:16px">未登録の信号です。ボタンとして登録できます。</div>
          <label for="slug">エンティティID</label>
          <div class="idrow"><span class="prefix">button.remolocal_</span>
            <input id="slug" placeholder="tv_power" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="40"></div>
          <div class="err" id="slugErr"></div>
          <p class="hint">「機器_操作」の形で入力します(例 tv_power、aircon_cool_26)。</p>
          <label for="alias">アクション名称</label>
          <p class="note" style="margin:0 0 6px">ダッシュボードの登録時に表示される名称、アイコン、エリアを以下に入力してください。</p>
          <input id="alias" placeholder="テレビ 電源" maxlength="80">
          <div id="regIconSlot" class="pick"></div><div id="regAreaSlot" class="pick"></div>
          <div class="row" style="margin-top:16px"><button class="primary" data-act="register">ボタンを追加</button></div>`;
      }
    }
    this._sec("secCapture", html);
    const slot = this.shadowRoot.getElementById("regIconSlot");
    if (slot) this._iconField(slot, this.s.regIcon, (v) => { this.s.regIcon = v; });
    const aslot = this.shadowRoot.getElementById("regAreaSlot");
    if (aslot) this._areaField(aslot, this.s.regArea, (v) => { this.s.regArea = v; });
  }

  _renderList() {
    const { buttons, buttonsErr } = this.s;
    let html = `<h2>登録済みのボタン</h2>`;
    if (buttonsErr) {
      html += `<div class="banner warn">${esc(buttonsErr)}</div>`;
    } else if (!buttons.length) {
      html += `<p class="empty">まだボタンがありません。信号を取得して登録すると、ここに並びます。</p>`;
    } else {
      html += `<ul class="list">${buttons.map((s) => `<li>
        <ha-icon icon="${esc(s.icon || "mdi:remote")}"></ha-icon>
        <div class="main"><div class="name">${esc(s.alias)}</div>
          <div class="sub meta"><span>${esc(s.entity_id)}</span><span>${esc(s.remo_name || s.remo)}</span>${s.signal ? `<span>${s.signal.length}要素</span>` : ""}</div>
          ${s.signal ? "" : `<div class="sub warn">信号データを読み取れません</div>`}
          </div>
        <div class="actions"><button data-act="sendButton" data-key="${esc(s.key)}">送信</button>
          <button data-act="editButton" data-key="${esc(s.key)}">編集</button>
          <button class="danger" data-act="deleteButton" data-key="${esc(s.key)}">削除</button></div></li>`).join("")}</ul>`;
    }
    this._sec("secList", html);
  }

  // ----------------------------------------------------------------- modals

  _openModal(m) { this.s.modal = m; this._renderModal(); }

  _closeModal() {
    this.s.modal = null;
    this._renderModal();
  }

  _remoOptions(selected) {
    const { remos } = this.s;
    const known = remos.some((r) => r.id === selected);
    return (known ? "" : `<option value="${esc(selected)}" selected>${esc(selected)}(未登録)</option>`) +
      remos.map((r) => `<option value="${esc(r.id)}"${r.id === selected ? " selected" : ""}>${esc(r.name)} (${esc(r.id)})</option>`).join("");
  }

  _renderModal() {
    const el = this.shadowRoot.getElementById("modal");
    const m = this.s.modal;
    if (!m) { el.innerHTML = ""; return; }
    let inner = "";
    if (m.type === "addRemo") {
      inner = `<h3>Remoを追加</h3>
        <p class="hint">mDNSで名前が見えるRemoから選びます。</p><div id="foundList">${this._foundHtml(m.found, m.pickedId)}</div>
        <label for="rName">表示名</label><input id="rName" placeholder="リビング" maxlength="40">
        <label>識別子</label><div class="idlabel" id="pickedLabel">${this._pickedHtml(m.pickedId)}</div>
        <details id="manual"><summary>一覧に出ない場合(手入力)</summary>
          <label for="rId">識別子(16進6桁)</label><input id="rId" placeholder="A35014" maxlength="6" autocomplete="off" spellcheck="false">
          <label for="rIp">IPアドレス</label><input id="rIp" placeholder="192.168.1.20" autocomplete="off">
          <dl class="explain">
            <dt>識別子だけ入力(一覧から選んだ場合も同じ)</dt>
            <dd>IPはARPから自動で特定し、以後も追従します。見つからない場合は「未検出」として登録され、「再読込」で再試行できます。</dd>
            <dt>IPだけ入力</dt>
            <dd>そのIPのMACから識別子を自動で決め、以後も追従します。MACを読めない場合は、識別子もあわせて入力してください。</dd>
            <dt>両方入力</dt>
            <dd>MACが識別子と一致するかを確認し、不一致なら登録しません。MACを読めない場合は、入力したIPで固定し、自動では更新しません(ルーターでIPの固定を推奨)。</dd>
          </dl></details>
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="primary" data-act="modalAddRemo">登録</button></div>`;
    } else if (m.type === "editRemo") {
      inner = `<h3>Remoの設定</h3>
        <label>識別子</label><div class="idlabel">${esc(m.id)}</div>
        <label for="rName">表示名</label><input id="rName" value="${esc(m.name)}" maxlength="40">
        <details${m.fixed ? " open" : ""}><summary>IPアドレスを手動で指定</summary>
          <label for="rIp">IPアドレス</label><input id="rIp" value="${esc(m.ip || "")}" autocomplete="off">
          <p class="explain">指定したIPのMACが識別子と一致すれば、自動追従を続けます。不一致なら保存しません。MACを読めない場合は、固定IPとなり、自動では更新されません。</p>
        </details>
        <div class="actions"><button class="danger left" data-act="modalDeleteRemo">削除</button>
          <button data-act="modalClose">キャンセル</button><button class="primary" data-act="modalSaveRemo">保存</button></div>`;
    } else if (m.type === "editButton") {
      inner = `<h3>${esc(m.entity_id)} を編集</h3>
        <p class="hint">エンティティIDの変更は、HAの「設定 → デバイスとサービス → エンティティ」から行ってください。</p>
        <label for="eAlias">アクション名称</label>
        <p class="note" style="margin:0 0 6px">ダッシュボードの登録時に表示される名称、アイコン、エリアを以下に入力してください。</p>
        <input id="eAlias" value="${esc(m.alias)}" maxlength="80">
        <div id="eIconSlot" class="pick"></div><div id="eAreaSlot" class="pick"></div>
        <label for="eRemo">送信先のRemo</label><select id="eRemo">${this._remoOptions(m.remo)}</select>
        <label>信号</label>
        <div class="facts" style="margin-top:0">${m.sig ? `<span>${fmtSig(m.sig)}</span>` : `<span class="warn">読み取れません</span>`}</div>
        <div class="row"><button data-act="modalTestCurrent">現在の信号をテスト送信</button>
          <button data-act="modalRecapture">信号を再取得して差し替え</button></div>
        ${m.newCap ? `<div class="banner ok" style="margin-top:12px">新しい信号を取得しました: ${fmtSig(m.newCap.summary)}.
          保存すると差し替わります。<div class="row" style="margin-top:8px"><button data-act="modalTestNew">新しい信号をテスト送信</button></div>
          ${m.newCap.same_as_previous ? `<div class="warn" style="margin-top:6px">前回取得した信号と完全に同じです。</div>` : ""}</div>` : ""}
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="primary" data-act="modalSaveButton">保存</button></div>`;
    } else if (m.type === "deleteButton") {
      inner = `<h3>削除の確認</h3><p>${esc(m.entity_id)}(${esc(m.alias)})を削除します。</p>
        <div id="refsBox">${this._refsHtml(m.refs)}</div>
        <p class="hint">このボタンのエンティティも、あわせて削除されます。</p>
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="danger" data-act="modalConfirmDelete">削除する</button></div>`;
    }
    el.innerHTML = `<div class="backdrop" data-act="modalBackdrop"><div class="dialog" role="dialog" aria-modal="true">${inner}</div></div>`;
    if (m.type === "editButton") {
      this._iconField(this.shadowRoot.getElementById("eIconSlot"), m.icon, (v) => { m.icon = v; });
      this._areaField(this.shadowRoot.getElementById("eAreaSlot"), m.area_id, (v) => { m.area_id = v; });
    }
  }

  _pickedHtml(id) {
    return id ? esc(id) : `<span class="hint">未選択(一覧から選ぶか、下の手入力を開いてください)</span>`;
  }

  _foundHtml(found, picked) {
    if (found === null) return `<p class="hint">検索中…</p>`;
    if (!found.length) return `<p class="hint">見つかりませんでした。識別子かIPアドレスを手入力してください。</p>`;
    return found
      .map((f) => `<button class="chip" data-act="pickFound" data-id="${esc(f.id)}" aria-pressed="${f.id === picked}"${f.registered ? " disabled" : ""}>Remo-${esc(f.id)}${f.registered ? "(登録済み)" : ""}</button>`)
      .join("");
  }

  _refsHtml(refs) {
    if (refs === null) return `<p class="hint">参照を確認中…</p>`;
    if (!refs.length) return `<p class="hint">他の設定からの参照は見つかりませんでした。</p>`;
    return `<div class="banner warn">次の場所から参照されています。削除すると動かなくなります。
      <ul class="refs">${refs.map((r) => `<li>${esc(r.file)} の ${r.line} 行目: ${esc(r.text)}</li>`).join("")}</ul></div>`;
  }

  _syncButtonModal() {
    const m = this.s.modal;
    if (!m || m.type !== "editButton") return;
    m.alias = this._q("eAlias");
    m.remo = this._q("eRemo") || m.remo;
  }

  // ----------------------------------------------------------------- events

  _onChange(e) {
    if (e.target.id === "remoSel") {
      this.s.sel = e.target.value;
      this.s.cap = null;
      this.s.regIcon = ""; this.s.regArea = "";
      this._renderRemo();
      this._renderCapture();
    }
  }

  _refreshPicked() {
    const m = this.s.modal;
    const box = this.shadowRoot.getElementById("foundList");
    if (box) box.innerHTML = this._foundHtml(m.found, m.pickedId);
    const lab = this.shadowRoot.getElementById("pickedLabel");
    if (lab) lab.innerHTML = this._pickedHtml(m.pickedId);
  }

  _onInput(e) {
    if (e.target.id === "rId" && this.s.modal && this.s.modal.type === "addRemo") {
      if (e.target.value.trim() && this.s.modal.pickedId) {
        this.s.modal.pickedId = "";
        this._refreshPicked();
      }
      return;
    }
    if (e.target.id !== "slug") return;
    const v = e.target.value;
    const ok = v === "" || SLUG_RE.test(v);
    this.shadowRoot.getElementById("slugErr").textContent = ok ? "" : "小文字英数字とアンダースコアのみ、40文字以内で入力してください";
    e.target.classList.toggle("invalid", !ok);
  }

  _onClick(e) {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;
    if (act === "modalBackdrop") {
      if (e.target === t) this._closeModal();
      return;
    }
    const key = t.dataset.key;
    const s = this.s;
    const handlers = {
      refresh: () => this._work(async () => {
        const r = await this._api("POST", "refresh", {});
        const before = s.remos;
        s.remos = r.remos;
        const nm = (id) => (before.find((x) => x.id === id) || r.remos.find((x) => x.id === id) || {}).name || id;
        const lines = r.results.filter((x) => x.changed || !x.new)
          .map((x) => (x.new ? `${nm(x.id)}: ${x.old || "未特定"} → ${x.new}` : `${nm(x.id)}: 見つかりません`));
        this._toast(lines.length ? `IPを更新しました\n${lines.join("\n")}` : "全てのRemoのIPは最新です");
        await this._loadRemos();
      }),
      addRemo: () => {
        this._openModal({ type: "addRemo", found: null, pickedId: "" });
        this._api("GET", "discover").then((r) => {
          if (!s.modal || s.modal.type !== "addRemo") return;
          s.modal.found = r.found;
          this._refreshPicked();
          // 選べる候補がないときは、手入力を開いておく
          if (!r.found.some((f) => !f.registered)) this.shadowRoot.getElementById("manual").open = true;
        }).catch(() => {
          if (!s.modal || s.modal.type !== "addRemo") return;
          s.modal.found = [];
          this._refreshPicked();
          this.shadowRoot.getElementById("manual").open = true;
        });
      },
      pickFound: () => {
        s.modal.pickedId = t.dataset.id;
        this.shadowRoot.getElementById("rId").value = "";
        this._refreshPicked();
      },
      editRemo: () => {
        const r = s.remos.find((x) => x.id === s.sel);
        if (r) this._openModal({ type: "editRemo", id: r.id, name: r.name, ip: r.ip, fixed: r.fixed });
      },
      modalClose: () => this._closeModal(),
      modalAddRemo: () => this._work(async () => {
        const r = await this._api("POST", "remos", {
          name: this._q("rName"), id: s.modal.pickedId || this._q("rId").toUpperCase() || undefined, ip: this._q("rIp") || undefined,
        });
        this._closeModal();
        s.sel = r.remo.id;
        await this._loadRemos();
        if (r.remo.status === "not_found") {
          this._toast(`${r.remo.name} (${r.remo.id}) を登録しましたが、ネットワーク上で特定できませんでした。\n` +
            "識別子の入力ミス、またはRemoの電源・Wi-Fi接続を確認してください。「再読込」で再試行できます。" +
            "間違って登録した場合は、「設定」から削除してください。", "warn");
        } else {
          this._toast(`${r.remo.name} を登録しました`);
        }
      }),
      modalSaveRemo: () => this._work(async () => {
        const m = s.modal;
        const ip = this._q("rIp");
        await this._api("PATCH", `remos/${encodeURIComponent(m.id)}`, { name: this._q("rName"), ip: ip && ip !== m.ip ? ip : undefined });
        this._closeModal();
        await this._loadRemos();
        this._toast("Remoの設定を保存しました");
      }),
      modalDeleteRemo: () => this._work(async () => {
        const m = s.modal;
        if (!window.confirm(`${m.name} を台帳から削除します。よろしいですか?`)) return;
        try {
          await this._api("DELETE", `remos/${encodeURIComponent(m.id)}`);
        } catch (err) {
          const used = err.body && err.body.buttons;
          if (err.status !== 409 || !used) throw err;
          if (!window.confirm(`このRemoを使うボタンが${used.length}件あります(${used.join(", ")})。それでも削除しますか?`)) return;
          await this._api("DELETE", `remos/${encodeURIComponent(m.id)}?force=1`);
        }
        this._closeModal();
        await this._loadRemos();
        this._toast("Remoを削除しました");
      }),
      capture: () => this._work(async () => {
        s.cap = await this._api("POST", "capture", { remo: s.sel });
        s.regIcon = ""; s.regArea = "";
        this._renderCapture();
      }),
      testSendCap: () => this._work(async () => {
        await this._api("POST", "test_send", { capture_id: s.cap.capture_id });
        this._toast("テスト送信しました");
      }),
      register: () => this._work(async () => {
        const slug = this._q("slug");
        if (!SLUG_RE.test(slug)) {
          this._toast("エンティティIDは小文字英数字とアンダースコアで入力してください", "error");
          return;
        }
        const r = await this._api("POST", "buttons", {
          capture_id: s.cap.capture_id, remo: s.cap.remo, slug, alias: this._q("alias"), icon: s.regIcon, area_id: s.regArea,
        });
        s.cap = null;
        s.regIcon = ""; s.regArea = "";
        this._renderCapture();
        await this._loadButtons();
        this._toast(`${r.entity_id} を追加しました`);
      }),
      sendButton: () => this._work(async () => {
        await this._api("POST", `buttons/${encodeURIComponent(key)}/send`, {});
        this._toast("送信しました");
      }),
      editButton: () => {
        const sc = s.buttons.find((x) => x.key === key);
        if (sc) this._openModal({ type: "editButton", key, entity_id: sc.entity_id, alias: sc.alias, icon: sc.icon, area_id: sc.area_id || "", remo: sc.remo, sig: sc.signal, newCap: null });
      },
      modalTestCurrent: () => this._work(async () => {
        await this._api("POST", `buttons/${encodeURIComponent(s.modal.key)}/send`, {});
        this._toast("現在の信号を送信しました");
      }),
      modalRecapture: () => this._work(async () => {
        this._syncButtonModal();
        const m = s.modal;
        m.newCap = await this._api("POST", "capture", { remo: m.remo });
        this._renderModal();
      }),
      modalTestNew: () => this._work(async () => {
        this._syncButtonModal();
        const m = s.modal;
        await this._api("POST", "test_send", { capture_id: m.newCap.capture_id, remo: m.remo });
        this._toast("新しい信号を送信しました");
      }),
      modalSaveButton: () => this._work(async () => {
        this._syncButtonModal();
        const m = s.modal;
        await this._api("PUT", `buttons/${encodeURIComponent(m.key)}`, {
          alias: m.alias, icon: m.icon || "", area_id: m.area_id || "", remo: m.remo, capture_id: m.newCap ? m.newCap.capture_id : undefined,
        });
        this._closeModal();
        await this._loadButtons();
        this._toast(`${m.entity_id} を保存しました`);
      }),
      deleteButton: () => {
        const sc = s.buttons.find((x) => x.key === key);
        if (!sc) return;
        this._openModal({ type: "deleteButton", key, entity_id: sc.entity_id, alias: sc.alias, refs: null });
        this._api("GET", `buttons/${encodeURIComponent(key)}/references`).then((r) => {
          if (!s.modal || s.modal.key !== key) return;
          s.modal.refs = r.references;
          const box = this.shadowRoot.getElementById("refsBox");
          if (box) box.innerHTML = this._refsHtml(r.references);
        }).catch((err) => this._toast(err.message, "error"));
      },
      modalConfirmDelete: () => this._work(async () => {
        const m = s.modal;
        const r = await this._api("DELETE", `buttons/${encodeURIComponent(m.key)}`);
        this._closeModal();
        await this._loadButtons();
        this._toast(`${m.entity_id} を削除しました` + (r.entity === "removed" ? "\nエンティティも削除しました。" : ""));
      }),
    };
    const fn = handlers[act];
    if (fn) fn();
  }
}

customElements.define("remo-ir-local-panel", RemoIrLocalPanel);
