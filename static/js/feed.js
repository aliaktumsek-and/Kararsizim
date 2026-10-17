// Poll feed: loads /api/polls/ page by page and renders cards.
// A card shows tappable options until the visitor has voted, then results.
// All user-supplied text is written with textContent (never innerHTML).
(function () {
  const feed = document.getElementById("feed");
  if (!feed) return;
  const status = document.getElementById("feed-status");
  const moreButton = document.getElementById("feed-more");
  let page = 0;
  let loading = false;
  let auth = { authenticated: false };

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

  // The option this visitor voted for: server-side for members, local for guests.
  function myChoice(poll) {
    return auth.authenticated ? poll.my_vote : window.PollVote.getLocalVote(poll.id);
  }

  function renderCard(poll) {
    const card = el("article", "card poll-card");
    card.dataset.pollId = poll.id;
    paint(card, poll);
    return card;
  }

  function paint(card, poll, errorMessage) {
    const mine = myChoice(poll);
    const hasVoted = mine !== null && mine !== undefined;
    const canChange = hasVoted && auth.authenticated;

    card.replaceChildren(
      el("h2", "poll-question", poll.question),
      el("p", "poll-meta", "@" + poll.author + " · " + timeAgo(poll.created_at))
    );

    const list = el("ul", "poll-options");
    poll.options.forEach((option, index) => {
      const item = el("li");
      const colorClass = "color-" + (index % 5);
      const isMine = hasVoted && option.id === mine;

      if (!hasVoted) {
        const button = el("button", "poll-option " + colorClass, option.text);
        button.type = "button";
        button.addEventListener("click", () => castVote(card, poll, option.id));
        item.append(button);
      } else {
        const tag = canChange ? "button" : "div";
        const row = el(tag, "poll-result " + colorClass + (isMine ? " is-mine" : ""));
        if (canChange) {
          row.type = "button";
          row.addEventListener("click", () => {
            if (!isMine) castVote(card, poll, option.id);
          });
        }
        const bar = el("span", "poll-bar");
        bar.setAttribute("aria-hidden", "true");
        const label = el("span", "poll-label", (isMine ? "✓ " : "") + option.text);
        const count = el("span", "poll-count", option.percent + "% · " + option.votes + " oy");
        row.append(bar, label, count);
        // Grow the bar from 0 so the result animates in.
        requestAnimationFrame(() =>
          requestAnimationFrame(() => (bar.style.width = option.percent + "%"))
        );
        item.append(row);
      }
      list.append(item);
    });
    card.append(list);

    const footer = el("p", "poll-total", poll.total_votes + " oy");
    if (canChange) footer.textContent += " · Oyunu değiştirmek için başka bir seçeneğe dokun";
    card.append(footer);

    if (errorMessage) {
      const error = el("p", "poll-error", errorMessage);
      error.setAttribute("role", "alert");
      card.append(error);
    }
  }

  async function castVote(card, poll, optionId) {
    card.querySelectorAll("button").forEach((button) => (button.disabled = true));
    const result = await window.PollVote.vote(poll.id, optionId, auth.authenticated);
    if (result.ok) {
      // Members get my_vote from the server; guests rely on the stored choice.
      paint(card, result.poll);
    } else {
      paint(card, poll, result.error);
    }
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
    data.polls.forEach((poll) => feed.append(renderCard(poll)));
    setStatus(feed.children.length ? "" : "Henüz anket yok. İlk anketi sen aç!");
    moreButton.textContent = "Daha fazla yükle";
    moreButton.hidden = !data.has_next;
  }

  moreButton.addEventListener("click", loadMore);
  loadMore();
})();
