// Create-poll form: dynamic 2-5 option inputs, counters, client-side checks
// that mirror the server rules, then POST /api/polls/.
(function () {
  const form = document.getElementById("create-form");
  if (!form) return;

  const MIN_OPTIONS = 2;
  const MAX_OPTIONS = 5;
  const QUESTION_MAX = 140;
  const OPTION_MAX = 60;

  const question = document.getElementById("question");
  const questionCount = document.getElementById("question-count");
  const list = document.getElementById("option-list");
  const addButton = document.getElementById("add-option");
  const submit = form.querySelector('button[type="submit"]');

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function optionInputs() {
    return Array.from(list.querySelectorAll("input"));
  }

  // Keep labels, remove buttons and the add button in sync with the row count.
  function refresh() {
    const rows = Array.from(list.children);
    rows.forEach((row, index) => {
      row.querySelector("input").setAttribute("aria-label", "Seçenek " + (index + 1));
      row.querySelector("button").hidden = rows.length <= MIN_OPTIONS;
      row.querySelector("button").setAttribute("aria-label", "Seçenek " + (index + 1) + " sil");
    });
    addButton.hidden = rows.length >= MAX_OPTIONS;
  }

  function addOption(focus) {
    if (list.children.length >= MAX_OPTIONS) return;
    const row = el("div", "option-row");
    const input = el("input");
    input.type = "text";
    input.name = "option";
    input.maxLength = OPTION_MAX;
    input.placeholder = "Seçenek " + (list.children.length + 1);
    input.autocomplete = "off";

    const remove = el("button", "option-remove", "✕");
    remove.type = "button";
    remove.addEventListener("click", () => {
      if (list.children.length <= MIN_OPTIONS) return;
      row.remove();
      refresh();
    });

    row.append(input, remove);
    list.append(row);
    refresh();
    if (focus) input.focus();
  }

  function showErrors(errors) {
    form.querySelectorAll("[data-error-for]").forEach((node) => {
      node.textContent = "";
      node.hidden = true;
    });
    for (const [field, messages] of Object.entries(errors)) {
      const target =
        form.querySelector('[data-error-for="' + field + '"]') ||
        form.querySelector('[data-error-for="__all__"]');
      if (!target) continue;
      target.textContent = (Array.isArray(messages) ? messages : [messages]).join(" ");
      target.hidden = false;
    }
  }

  // Same rules as the server; returns {} when everything is valid.
  function validate(text, options) {
    const errors = {};
    if (!text) errors.question = ["Soru boş olamaz."];
    const problems = [];
    if (options.some((o) => !o)) problems.push("Seçenekler boş olamaz.");
    const lowered = options.filter(Boolean).map((o) => o.toLocaleLowerCase("tr"));
    if (new Set(lowered).size !== lowered.length) problems.push("Aynı seçenek birden fazla kez eklenmiş.");
    if (problems.length) errors.options = problems;
    return errors;
  }

  question.addEventListener("input", () => {
    questionCount.textContent = question.value.length;
  });
  addButton.addEventListener("click", () => addOption(true));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = question.value.trim();
    const options = optionInputs().map((input) => input.value.trim());

    const errors = validate(text, options);
    showErrors(errors);
    if (Object.keys(errors).length) return;

    submit.disabled = true;
    const { ok, status, data } = await window.api.post("/api/polls/", { question: text, options });
    if (ok) {
      window.location.assign("/");
      return;
    }
    if (status === 401) {
      window.location.assign("/giris/?next=/olustur/");
      return;
    }
    showErrors((data && data.errors) || { __all__: ["Bir şeyler ters gitti."] });
    submit.disabled = false;
  });

  addOption(false);
  addOption(false);
  question.focus();
})();
