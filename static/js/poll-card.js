// Shared poll card used by the feed and the single-poll page.
// Layout: question, author/time, multi-color vote meter, verdict + count, then
// option chips. Chips are tappable until the visitor has voted.
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

  function timeLeft(iso) {
    const minutes = Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 60000));
    if (minutes < 1) return "1 dk'dan az kaldı";
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return (hours ? hours + " sa " : "") + (rest ? rest + " dk " : "") + "kaldı";
  }

  // One-line summary of how the vote is going.
  function verdict(poll) {
    if (!poll.total_votes) return "Henüz oy yok";
    const sorted = poll.options.slice().sort((a, b) => b.votes - a.votes);
    const top = sorted[0].percent;
    const second = sorted[1].percent;
    if (top >= 60) return "Karar net";
    if (top - second <= 10) {
      return poll.options.length >= 3 && top < 40 ? "Kalabalık da kararsız" : "Az farkla önde";
    }
    return "Önde gidiyor";
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

  function renderMeter(poll) {
    const meter = el("div", "poll-meter");
    meter.setAttribute("role", "img");
    meter.setAttribute(
      "aria-label",
      poll.total_votes
        ? "Oy dağılımı: " + poll.options.map((o) => o.text + " %" + o.percent).join(", ")
        : "Henüz oy yok"
    );
    poll.options.forEach((option, index) => {
      if (!option.votes) return;
      const segment = el("span", "seg color-" + (index % 5));
      meter.append(segment);
      // Grow from 0 so the distribution animates in.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => (segment.style.flexGrow = option.votes))
      );
    });
    return meter;
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
    const closed = poll.is_closed;
    const canChange = hasVoted && ctx.auth.authenticated && !closed;

    const when = el("a", "poll-time", timeAgo(poll.created_at));
    when.href = "/anket/" + poll.id + "/";
    const meta = el("p", "poll-meta");
    meta.append("@" + poll.author + " · ", when);
    if (closed) {
      meta.append(" · ", el("span", "poll-closed", "Kapalı"));
    } else if (poll.closes_at) {
      meta.append(" · " + timeLeft(poll.closes_at));
    }

    card.replaceChildren(el("h2", "poll-question", poll.question), meta, renderMeter(poll));
    card.append(el("p", "poll-verdict", verdict(poll)));
    card.append(el("p", "poll-count", poll.total_votes + " kişi oy verdi"));

    const chips = el("ul", "poll-chips");
    poll.options.forEach((option, index) => {
      const isMine = hasVoted && option.id === mine;
      const classes = "poll-chip color-" + (index % 5) + (isMine ? " is-mine" : "");
      const interactive = !closed && (!hasVoted || canChange);
      const chip = el(interactive ? "button" : "div", classes);
      chip.append(el("span", "chip-dot"), el("span", "chip-text", (isMine ? "✓ " : "") + option.text));
      // Percentages are revealed after voting, and always once the poll is closed.
      if (hasVoted || closed) chip.append(el("span", "chip-pct", option.percent + "%"));

      if (interactive) {
        chip.type = "button";
        if (canChange) chip.setAttribute("aria-pressed", String(isMine));
        chip.addEventListener("click", () => {
          if (!isMine) castVote(card, poll, ctx, option.id);
        });
      }
      const item = el("li");
      item.append(chip);
      chips.append(item);
    });
    card.append(chips);

    if (canChange) card.append(el("p", "poll-hint", "Oyunu değiştirmek için başka bir seçeneğe dokun."));

    const actions = el("div", "poll-actions");
    if (ctx.share) {
      const share = el("button", "btn btn-ghost btn-outline btn-sm", "Bağlantıyı kopyala");
      share.type = "button";
      share.addEventListener("click", () => copyLink(poll, share));
      actions.append(share);
    }
    const isOwner = ctx.auth.authenticated && ctx.auth.username === poll.author;
    if (isOwner && !closed) {
      const close = el("button", "btn btn-ghost btn-outline btn-sm", "Anketi kapat");
      close.type = "button";
      close.addEventListener("click", () => closePoll(card, poll, ctx, close));
      actions.append(close);
    }
    if (isOwner) {
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
      // A closed poll comes back with its fresh state so the card redraws as closed.
      paint(card, result.poll || poll, ctx, result.error);
    }
  }

  async function closePoll(card, poll, ctx, button) {
    if (!window.confirm("Anketi kapatmak istediğine emin misin? Kapanan ankete artık oy verilemez.")) return;
    button.disabled = true;
    const { ok, data } = await window.api.post("/api/polls/" + poll.id + "/close/");
    if (ok && data && data.id) {
      paint(card, data, ctx);
      return;
    }
    const errors = data && data.errors;
    const first = errors && Object.values(errors)[0];
    paint(card, poll, ctx, (first && first[0]) || "Anket kapatılamadı. Lütfen tekrar dene.");
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
