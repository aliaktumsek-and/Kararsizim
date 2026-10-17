// Header auth state + login / register forms. All user-supplied text is
// written with textContent (never innerHTML).
(function () {
  function safeNext() {
    const next = new URLSearchParams(window.location.search).get("next") || "";
    return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")
      ? next
      : "/";
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function withNext(path) {
    const next = new URLSearchParams(window.location.search).get("next");
    return next ? path + "?next=" + encodeURIComponent(next) : path;
  }

  // --- Header ---

  function renderNav(nav, state) {
    nav.replaceChildren();
    if (state.authenticated) {
      nav.append(el("span", "nav-user", "@" + state.username));
      const logout = el("button", "btn btn-ghost", "Çıkış");
      logout.type = "button";
      logout.addEventListener("click", async () => {
        logout.disabled = true;
        await window.api.post("/api/auth/logout/");
        window.location.assign("/");
      });
      nav.append(logout);
    } else {
      const login = el("a", "btn btn-ghost", "Giriş");
      login.href = "/giris/";
      const register = el("a", "btn btn-primary btn-sm", "Kayıt ol");
      register.href = "/kayit/";
      nav.append(login, register);
    }
  }

  async function initNav() {
    const nav = document.getElementById("auth-nav");
    if (!nav) return;
    const { ok, data } = await window.api.get("/api/auth/me/");
    renderNav(nav, ok && data ? data : { authenticated: false });
  }

  // --- Forms ---

  function showErrors(form, errors) {
    form.querySelectorAll("[data-error-for]").forEach((node) => {
      node.textContent = "";
      node.hidden = true;
    });
    form.querySelectorAll("input").forEach((input) => input.removeAttribute("aria-invalid"));

    for (const [field, messages] of Object.entries(errors || {})) {
      const target =
        form.querySelector('[data-error-for="' + field + '"]') ||
        form.querySelector('[data-error-for="__all__"]');
      if (!target) continue;
      const text = Array.isArray(messages) ? messages.join(" ") : String(messages);
      target.textContent = target.textContent ? target.textContent + " " + text : text;
      target.hidden = false;
      const input = form.querySelector('[name="' + field + '"]');
      if (input) input.setAttribute("aria-invalid", "true");
    }
  }

  function initForm(form) {
    const kind = form.dataset.authForm; // "login" | "register"
    const endpoint = "/api/auth/" + kind + "/";
    const submit = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {};
      new FormData(form).forEach((value, key) => {
        payload[key] = value;
      });

      submit.disabled = true;
      const { ok, data } = await window.api.post(endpoint, payload);
      if (ok) {
        window.location.assign(safeNext());
        return;
      }
      showErrors(form, (data && data.errors) || { __all__: ["Bir şeyler ters gitti."] });
      submit.disabled = false;
    });
  }

  document.querySelectorAll("form[data-auth-form]").forEach(initForm);
  document.querySelectorAll("[data-keep-next]").forEach((link) => {
    link.setAttribute("href", withNext(link.getAttribute("href")));
  });
  initNav();
})();
