// Poll feed: tabs (newest / popular), paging and cards (see poll-card.js).
(function () {
  const feed = document.getElementById("feed");
  if (!feed) return;
  const status = document.getElementById("feed-status");
  const moreButton = document.getElementById("feed-more");
  const tabs = Array.from(document.querySelectorAll("[data-sort]"));

  let sort = "new";
  let page = 0;
  let loading = false;
  let generation = 0; // bumped on tab change so late responses are ignored
  let auth = { authenticated: false, username: null };

  const EMPTY_MESSAGE = "Henüz anket yok. İlk anketi sen aç!";

  function setStatus(message) {
    status.textContent = message || "";
    status.hidden = !message;
  }

  function onDelete(card) {
    card.remove();
    if (!feed.children.length) setStatus(EMPTY_MESSAGE);
  }

  async function loadMore() {
    if (loading) return;
    loading = true;
    const mine = generation;
    moreButton.disabled = true;
    if (page === 0) setStatus("Anketler yükleniyor…");

    const url = "/api/polls/?page=" + (page + 1) + (sort === "popular" ? "&sort=popular" : "");
    const [authState, response] = await Promise.all([window.authReady, window.api.get(url)]);
    if (mine !== generation) return; // a tab switch started a newer load

    auth = authState;
    const { ok, data } = response;
    loading = false;
    moreButton.disabled = false;

    if (!ok || !data) {
      setStatus("Anketler yüklenemedi. Lütfen tekrar dene.");
      moreButton.textContent = "Tekrar dene";
      moreButton.hidden = false;
      return;
    }

    page = data.page;
    data.polls.forEach((poll) => feed.append(window.PollCard.create(poll, { auth, onDelete })));
    setStatus(feed.children.length ? "" : EMPTY_MESSAGE);
    moreButton.textContent = "Daha fazla yükle";
    moreButton.hidden = !data.has_next;
  }

  function selectTab(next) {
    if (next === sort) return;
    sort = next;
    tabs.forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.sort === sort)));
    generation += 1;
    loading = false;
    page = 0;
    feed.replaceChildren();
    moreButton.hidden = true;
    loadMore();
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.sort)));
  moreButton.addEventListener("click", loadMore);
  loadMore();
})();
