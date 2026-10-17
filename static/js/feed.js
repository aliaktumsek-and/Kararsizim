// Poll feed: loads /api/polls/ page by page and renders cards (see poll-card.js).
(function () {
  const feed = document.getElementById("feed");
  if (!feed) return;
  const status = document.getElementById("feed-status");
  const moreButton = document.getElementById("feed-more");
  let page = 0;
  let loading = false;
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
    moreButton.disabled = true;
    if (page === 0) setStatus("Anketler yükleniyor…");

    const [authState, response] = await Promise.all([
      window.authReady,
      window.api.get("/api/polls/?page=" + (page + 1)),
    ]);
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

  moreButton.addEventListener("click", loadMore);
  loadMore();
})();
