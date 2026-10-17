// Poll feed: tabs (newest / popular / closed), paging and cards (see poll-card.js).
(function () {
  const feed = document.getElementById("feed");
  if (!feed) return;
  const status = document.getElementById("feed-status");
  const moreButton = document.getElementById("feed-more");
  const tabs = Array.from(document.querySelectorAll("[data-sort]"));

  let tab = "new";
  let page = 0;
  let loading = false;
  let generation = 0; // bumped on tab change so late responses are ignored
  let auth = { authenticated: false, username: null };

  const EMPTY_MESSAGES = {
    new: "Henüz anket yok. İlk anketi sen aç!",
    popular: "Henüz anket yok. İlk anketi sen aç!",
    closed: "Henüz kapanan anket yok.",
  };
  const QUERIES = { new: "", popular: "&sort=popular", closed: "&status=closed" };

  function setStatus(message) {
    status.textContent = message || "";
    status.hidden = !message;
  }

  function onDelete(card) {
    card.remove();
    if (!feed.children.length) setStatus(EMPTY_MESSAGES[tab]);
  }

  async function loadMore() {
    if (loading) return;
    loading = true;
    const mine = generation;
    moreButton.disabled = true;
    if (page === 0) setStatus("Anketler yükleniyor…");

    const url = "/api/polls/?page=" + (page + 1) + QUERIES[tab];
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
    setStatus(feed.children.length ? "" : EMPTY_MESSAGES[tab]);
    moreButton.textContent = "Daha fazla yükle";
    moreButton.hidden = !data.has_next;
  }

  function selectTab(next) {
    if (next === tab) return;
    tab = next;
    tabs.forEach((button) => button.setAttribute("aria-selected", String(button.dataset.sort === tab)));
    generation += 1;
    loading = false;
    page = 0;
    feed.replaceChildren();
    moreButton.hidden = true;
    loadMore();
  }

  tabs.forEach((button) => button.addEventListener("click", () => selectTab(button.dataset.sort)));
  moreButton.addEventListener("click", loadMore);
  loadMore();
})();
