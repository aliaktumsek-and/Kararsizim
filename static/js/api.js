// Small fetch helper: JSON in/out, CSRF header for unsafe methods.
(function () {
  function getCookie(name) {
    const prefix = name + "=";
    for (const part of document.cookie.split(";")) {
      const cookie = part.trim();
      if (cookie.startsWith(prefix)) {
        return decodeURIComponent(cookie.slice(prefix.length));
      }
    }
    return "";
  }

  // Resolves to { ok, status, data }. Never throws on HTTP errors; network
  // failures resolve to { ok: false, status: 0, data: { errors } }.
  async function api(method, url, body) {
    const headers = { Accept: "application/json" };
    const options = { method, headers, credentials: "same-origin" };
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = getCookie("csrftoken");
      options.body = JSON.stringify(body || {});
    }
    try {
      const response = await fetch(url, options);
      let data = null;
      try {
        data = await response.json();
      } catch (e) {
        data = null;
      }
      return { ok: response.ok, status: response.status, data };
    } catch (e) {
      return {
        ok: false,
        status: 0,
        data: { errors: { __all__: ["Bağlantı hatası. Lütfen tekrar dene."] } },
      };
    }
  }

  window.api = {
    get: (url) => api("GET", url),
    post: (url, body) => api("POST", url, body),
    del: (url) => api("DELETE", url),
  };
})();
