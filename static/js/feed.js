// Poll feed: loads /api/polls/ page by page and renders cards.
// All user-supplied text is written with textContent (never innerHTML).
(function () {
  const feed = document.getElementById("feed");
  if (!feed) return;
  const status = document.getElementById("feed-status");
  const moreButton = document.getElementById("feed-more");
  let page = 0;
  let loading = false;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function timeAgo(iso) {
    const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    if (seconds < 60) return "az önce";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + " dk önce";
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + " sa önce";
    const days = Math.floor(hours / 24);
    if (days < 30) return days + " gün önce";
    return new Date(iso).toLocaleDateString("tr-TR");
  }

  function renderCard(poll) {
    const card = el("article", "card poll-card");
    card.dataset.pollId = poll.id;

    card.append(el("h2", "poll-question", poll.question));
    card.append(el("p", "poll-meta", "@" + poll.author + " · " + timeAgo(poll.created_at)));

    const list = el("ul", "poll-options");
    poll.options.forEach((option, index) => {
      const item = el("li", "poll-option color-" + (index % 5), option.text);
      item.dataset.optionId = option.id;
      list.append(item);
    });
    card.append(list);

    const total = poll.total_votes;
    card.append(el("p", "poll-total", total + " oy"));
    return card;
  }

  function setStatus(message) {
    status.textContent = message || "";
    status.hidden = !message;
  }

  async function loadMore() {
    if (loading) return;
    loading = true;
    moreButton.disabled = true;
    if (page === 0) setStatus("Anketler yükleniyor…");

    const { ok, data } = await window.api.get("/api/polls/?page=" + (page + 1));
    loading = false;
    moreButton.disabled = false;

    if (!ok || !data) {
      setStatus("Anketler yüklenemedi. Lütfen tekrar dene.");
      moreButton.textContent = "Tekrar dene";
      moreButton.hidden = false;
      return;
    }

    page = data.page;
    data.polls.forEach((poll) => feed.append(renderCard(poll)));
    setStatus(feed.children.length ? "" : "Henüz anket yok. İlk anketi sen aç!");
    moreButton.textContent = "Daha fazla yükle";
    moreButton.hidden = !data.has_next;
  }

  moreButton.addEventListener("click", loadMore);
  loadMore();
})();
