// Single-poll page: renders one shareable card.
(function () {
  const holder = document.getElementById("poll");
  if (!holder) return;
  const status = document.getElementById("poll-status");

  async function load() {
    const [auth, response] = await Promise.all([
      window.authReady,
      window.api.get("/api/polls/" + holder.dataset.pollId + "/"),
    ]);
    const { ok, status: code, data } = response;

    if (!ok || !data) {
      status.textContent =
        code === 404 ? "Bu anket bulunamadı. Silinmiş olabilir." : "Anket yüklenemedi. Lütfen tekrar dene.";
      status.hidden = false;
      return;
    }

    status.hidden = true;
    holder.append(
      window.PollCard.create(data, {
        auth,
        share: true,
        onDelete: () => window.location.assign("/"),
      })
    );
  }

  load();
})();
