// Shared poll card used by the feed and the single-poll page.
// A card shows tappable options until the visitor has voted, then results.
// All user-supplied text is written with textContent (never innerHTML).
//
// PollCard.create(poll, ctx) -> <article>
//   ctx.auth      { authenticated, username }
//   ctx.share     show a "copy link" button
//   ctx.onDelete  (card, poll) called after the owner deleted the poll
(function () {
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
  function myChoice(poll, ctx) {
    return ctx.auth.authenticated ? poll.my_vote : window.PollVote.getLocalVote(poll.id);
  }

  function pollUrl(poll) {
    return window.location.origin + "/anket/" + poll.id + "/";
  }

  async function copyLink(poll, button) {
    const url = pollUrl(poll);
    try {
      await navigator.clipboard.writeText(url);
      button.textContent = "Kopyalandı ✓";
      setTimeout(() => (button.textContent = "Bağlantıyı kopyala"), 2000);
    } catch (e) {
      window.prompt("Bağlantıyı kopyala:", url);
    }
  }

  function create(poll, ctx) {
    const card = el("article", "card poll-card");
    card.dataset.pollId = poll.id;
    paint(card, poll, ctx);
    return card;
  }

  function paint(card, poll, ctx, errorMessage) {
    const mine = myChoice(poll, ctx);
    const hasVoted = mine !== null && mine !== undefined;
    const canChange = hasVoted && ctx.auth.authenticated;

    const when = el("a", "poll-time", timeAgo(poll.created_at));
    when.href = "/anket/" + poll.id + "/";
    const meta = el("p", "poll-meta");
    meta.append("@" + poll.author + " · ", when);
    card.replaceChildren(el("h2", "poll-question", poll.question), meta);

    const list = el("ul", "poll-options");
    poll.options.forEach((option, index) => {
      const item = el("li");
      const colorClass = "color-" + (index % 5);
      const isMine = hasVoted && option.id === mine;

      if (!hasVoted) {
        const button = el("button", "poll-option " + colorClass, option.text);
        button.type = "button";
        button.addEventListener("click", () => castVote(card, poll, ctx, option.id));
        item.append(button);
      } else {
        const row = el(canChange ? "button" : "div", "poll-result " + colorClass + (isMine ? " is-mine" : ""));
        if (canChange) {
          row.type = "button";
          row.setAttribute("aria-pressed", String(isMine));
          row.addEventListener("click", () => {
            if (!isMine) castVote(card, poll, ctx, option.id);
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

    const total = poll.total_votes + " oy";
    card.append(
      el("p", "poll-total", canChange ? total + " · Oyunu değiştirmek için başka bir seçeneğe dokun" : total)
    );

    const actions = el("div", "poll-actions");
    if (ctx.share) {
      const share = el("button", "btn btn-ghost btn-outline btn-sm", "Bağlantıyı kopyala");
      share.type = "button";
      share.addEventListener("click", () => copyLink(poll, share));
      actions.append(share);
    }
    if (ctx.auth.authenticated && ctx.auth.username === poll.author) {
      const remove = el("button", "btn btn-ghost btn-danger btn-sm", "Sil");
      remove.type = "button";
      remove.addEventListener("click", () => deletePoll(card, poll, ctx, remove));
      actions.append(remove);
    }
    if (actions.children.length) card.append(actions);

    if (errorMessage) {
      const error = el("p", "poll-error", errorMessage);
      error.setAttribute("role", "alert");
      card.append(error);
    }
  }

  async function castVote(card, poll, ctx, optionId) {
    card.querySelectorAll("button").forEach((button) => (button.disabled = true));
    const result = await window.PollVote.vote(poll.id, optionId, ctx.auth.authenticated);
    if (result.ok) {
      paint(card, result.poll, ctx);
    } else {
      paint(card, poll, ctx, result.error);
    }
  }

  async function deletePoll(card, poll, ctx, button) {
    if (!window.confirm("Bu anketi silmek istediğine emin misin? Bu işlem geri alınamaz.")) return;
    button.disabled = true;
    const { ok, data } = await window.api.del("/api/polls/" + poll.id + "/");
    if (ok) {
      if (ctx.onDelete) ctx.onDelete(card, poll);
      return;
    }
    const errors = data && data.errors;
    const first = errors && Object.values(errors)[0];
    paint(card, poll, ctx, (first && first[0]) || "Anket silinemedi. Lütfen tekrar dene.");
  }

  window.PollCard = { create };
})();
