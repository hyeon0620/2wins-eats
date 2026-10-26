/* 画面共通の小さな道具。API を呼ぶ、金額を整える、エラーを出す、確認ダイアログ。 */
window.Eats = {
  async api(method, url, body) {
    const init = { method, credentials: "same-origin", headers: {} };
    if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    const res = await fetch(url, init);
    let data = null;
    try { data = await res.json(); } catch (e) { /* 204 など本文なし */ }
    if (!res.ok) {
      let message = data && data.detail;
      if (Array.isArray(message)) message = message.map(m => (m.loc ? m.loc.slice(-1)[0] + ": " : "") + m.msg).join("、");
      const err = new Error(message || "エラーが起きました（" + res.status + "）");
      err.status = res.status;
      err.code = data && data.code;
      err.data = data;
      throw err;
    }
    return data;
  },
  yen(n) { return "¥" + Number(n || 0).toLocaleString("ja-JP"); },
  showError(el, message) { if (!el) return; el.textContent = message || ""; el.hidden = !message; },
  confirmReplace(message, onConfirm) {
    const modal = document.getElementById("conflict-modal");
    if (!modal) { if (confirm(message)) onConfirm(); return; }
    document.getElementById("conflict-message").textContent = message;
    modal.hidden = false;
    const keep = document.getElementById("conflict-keep");
    const replace = document.getElementById("conflict-replace");
    const close = () => { modal.hidden = true; keep.onclick = null; replace.onclick = null; };
    keep.onclick = close;
    replace.onclick = () => { close(); onConfirm(); };
  },
};
