// Voting: POST a vote and remember anonymous votes in this browser only.
// The server never tracks anonymous voters; localStorage just discourages
// repeat votes (a prototype trade-off, easy to bypass by clearing site data).
(function () {
  const KEY_PREFIX = "voted_";

  function getLocalVote(pollId) {
    try {
      const value = window.localStorage.getItem(KEY_PREFIX + pollId);
      return value === null ? null : Number(value);
    } catch (e) {
      return null;
    }
  }

  function setLocalVote(pollId, optionId) {
    try {
      window.localStorage.setItem(KEY_PREFIX + pollId, String(optionId));
    } catch (e) {
      // Storage unavailable (private mode etc.): the vote still counted.
    }
  }

  // Resolves to { ok, poll, error } (poll is also set when the poll turned out to be closed). Anonymous successes are remembered locally.
  async function vote(pollId, optionId, authenticated) {
    const { ok, data } = await window.api.post("/api/polls/" + pollId + "/vote/", {
      option_id: optionId,
    });
    if (!ok || !data || !data.id) {
      const errors = data && data.errors;
      const first = errors && Object.values(errors)[0];
      return {
        ok: false,
        error: (first && first[0]) || "Oy verilemedi. Lütfen tekrar dene.",
        poll: data && data.poll ? data.poll : null,
      };
    }
    if (!authenticated) setLocalVote(pollId, optionId);
    return { ok: true, poll: data };
  }

  window.PollVote = { getLocalVote, vote };
})();
