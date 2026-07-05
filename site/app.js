const STORAGE_KEY = "asd-radar-preferences-v2";
const elements = {};
const data = window.RESEARCH_DATA || {};
const pageConfig = window.RESEARCH_PAGE_CONFIG || { activeTopic: "all", pathPrefix: "" };

const state = {
  allArticles: Array.isArray(data.papers) ? data.papers : [],
  filteredArticles: [],
  view: "queue",
  activeTopic: pageConfig.activeTopic || "all"
};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  renderTopicLinks();
  renderFilters();
  hydrateDefaults();
  loadPreferences();
  bindEvents();
  applyFilters();
  updateQueryPreview();
  if (window.lucide) {
    window.lucide.createIcons();
  }
});

function cacheElements() {
  [
    "refresh-button",
    "copy-query-button",
    "copy-digest-button",
    "export-button",
    "reset-button",
    "select-journals-button",
    "date-window",
    "max-results",
    "bucket-filters",
    "topic-filters",
    "age-filters",
    "journal-filters",
    "article-list",
    "source-status",
    "last-updated",
    "metric-total",
    "metric-accepted",
    "metric-watchlist",
    "metric-under25",
    "sort-order",
    "query-output",
    "journal-output",
    "digest-output",
    "digest-count",
    "topic-links"
  ].forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function renderTopicLinks() {
  if (!elements["topic-links"]) return;
  const pathPrefix = pageConfig.pathPrefix || "";
  const links = (data.study_types || []).map((item) => {
    const link = document.createElement("a");
    link.className = `topic-link${item.slug === state.activeTopic ? " active" : ""}`;
    link.href = item.slug === "all" ? `${pathPrefix}index.html` : `${pathPrefix}topics/${item.slug}/`;
    link.innerHTML = `<span>${item.label}</span><b>${item.count}</b>`;
    return link;
  });
  elements["topic-links"].replaceChildren(...links);
}

function renderFilters() {
  renderFilterGroup("bucket-filters", data.bucket_options || [], "bucket", (item) => item.label, (item) => `${item.count} papers`);
  renderFilterGroup("topic-filters", (data.study_types || []).filter((item) => item.slug !== "all"), "topic", (item) => item.label, (item) => item.description);
  renderFilterGroup("age-filters", data.age_tags || [], "age", (item) => item.label, (item) => `${item.count} papers`);
  renderFilterGroup("journal-filters", data.journals || [], "journal", (item) => item.label, (item) => `${item.count} papers • ${item.tier}`);
}

function renderFilterGroup(containerId, items, group, labelFn, hintFn) {
  const container = elements[containerId];
  if (!container) return;
  container.replaceChildren(...items.map((item) => makeFilterOption(item, group, labelFn(item), hintFn ? hintFn(item) : "")));
}

function makeFilterOption(item, group, label, hint) {
  const option = document.createElement("label");
  option.className = "filter-option";

  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = item.id || item.slug || item.label;
  input.dataset.group = group;
  input.checked = group !== "bucket" || input.value !== "excluded";
  if (group === "topic" && state.activeTopic !== "all") {
    input.checked = input.value === state.activeTopic;
    input.disabled = input.value !== state.activeTopic;
  }

  const text = document.createElement("span");
  text.textContent = label;
  if (hint) {
    const small = document.createElement("small");
    small.textContent = hint;
    text.appendChild(small);
  }

  option.append(input, text);
  return option;
}

function hydrateDefaults() {
  elements["date-window"].value = String(data.run?.days || 14);
  elements["max-results"].value = String(Math.min(data.run?.max_results || Math.max(state.allArticles.length, 50), 250));
  elements["source-status"].textContent = state.allArticles.length ? "Static export ready" : "No screened papers";
  if (data.generated_at) {
    elements["last-updated"].textContent = `Generated ${data.generated_at}`;
  }
}

function bindEvents() {
  elements["refresh-button"].addEventListener("click", () => {
    window.location.reload();
  });
  elements["copy-query-button"].addEventListener("click", () => copyText(data.run?.query || "", "Search query copied"));
  elements["copy-digest-button"].addEventListener("click", () => copyText(buildDigest(), "Weekly digest copied"));
  elements["export-button"].addEventListener("click", exportCsv);
  elements["reset-button"].addEventListener("click", resetPreferences);
  elements["select-journals-button"].addEventListener("click", selectAllJournals);
  elements["sort-order"].addEventListener("change", () => renderArticles(state.filteredArticles));

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => setView(tab.dataset.view));
  });

  document.querySelectorAll("input, select").forEach((control) => {
    control.addEventListener("change", () => {
      savePreferences();
      applyFilters();
      updateQueryPreview();
    });
  });
}

function loadPreferences() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  if (!saved) return;

  if (saved.days) elements["date-window"].value = String(saved.days);
  if (saved.maxResults) elements["max-results"].value = String(saved.maxResults);
  applyCheckedValues("bucket", saved.buckets);
  applyCheckedValues("topic", saved.topics);
  applyCheckedValues("age", saved.ages);
  applyCheckedValues("journal", saved.journals);
}

function applyCheckedValues(group, values) {
  if (!Array.isArray(values)) return;
  document.querySelectorAll(`input[data-group="${group}"]`).forEach((input) => {
    if (!input.disabled) {
      input.checked = values.includes(input.value);
    }
  });
}

function savePreferences() {
  const prefs = {
    days: Number(elements["date-window"].value),
    maxResults: Number(elements["max-results"].value),
    buckets: selectedIds("bucket"),
    topics: selectedIds("topic"),
    ages: selectedIds("age"),
    journals: selectedIds("journal")
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

function resetPreferences() {
  localStorage.removeItem(STORAGE_KEY);
  document.querySelectorAll('input[data-group="bucket"]').forEach((input) => {
    input.checked = input.value !== "excluded";
  });
  document.querySelectorAll('input[data-group="topic"]').forEach((input) => {
    input.checked = state.activeTopic === "all" ? true : input.value === state.activeTopic;
  });
  document.querySelectorAll('input[data-group="age"], input[data-group="journal"]').forEach((input) => {
    input.checked = true;
  });
  elements["date-window"].value = String(data.run?.days || 14);
  elements["max-results"].value = String(Math.min(data.run?.max_results || Math.max(state.allArticles.length, 50), 250));
  applyFilters();
  updateQueryPreview();
}

function selectAllJournals() {
  document.querySelectorAll('input[data-group="journal"]').forEach((input) => {
    input.checked = true;
  });
  savePreferences();
  applyFilters();
  updateQueryPreview();
}

function selectedIds(group) {
  return [...document.querySelectorAll(`input[data-group="${group}"]:checked`)].map((input) => input.value);
}

function applyFilters() {
  const days = Number(elements["date-window"].value);
  const maxResults = clamp(Number(elements["max-results"].value), 10, 250);
  const buckets = new Set(selectedIds("bucket"));
  const topics = new Set(selectedIds("topic"));
  const ages = new Set(selectedIds("age"));
  const journals = new Set(selectedIds("journal"));

  const filtered = state.allArticles.filter((article) => {
    if (buckets.size && !buckets.has(article.bucket)) return false;
    if (state.activeTopic !== "all" && !paperMatchesLockedTopic(article, state.activeTopic)) return false;
    if (topics.size && !topics.has(article.study_type_slug)) return false;
    if (ages.size && article.age_tags.length && !article.age_tags.some((tag) => ages.has(tag))) return false;
    if (ages.size && !article.age_tags.length) return false;
    if (journals.size && !journals.has(slugify(article.journal))) return false;
    if (!withinDays(article.publication_date, days)) return false;
    return true;
  });

  state.filteredArticles = filtered.sort(sortArticles).slice(0, maxResults);
  renderArticles(state.filteredArticles);
}

function paperMatchesLockedTopic(article, topic) {
  if (topic === "therapy") return article.study_type_group === "therapy";
  if (topic === "non-therapy") return article.study_type_group === "non_therapy";
  return article.study_type_slug === topic;
}

function sortArticles(a, b) {
  const order = elements["sort-order"].value;
  if (order === "date") return compareDates(b.publication_date, a.publication_date) || b.display_score - a.display_score;
  if (order === "journal") return a.journal.localeCompare(b.journal) || b.display_score - a.display_score;
  return b.display_score - a.display_score || compareDates(b.publication_date, a.publication_date);
}

function renderArticles(articles) {
  elements["article-list"].replaceChildren();
  updateMetrics(articles);
  updateDigest();

  if (!articles.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>No articles in the current queue</strong><span>Try a wider window or broader filters.</span>";
    elements["article-list"].append(empty);
    return;
  }

  articles.forEach((article) => {
    elements["article-list"].append(renderArticleCard(article));
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderArticleCard(article) {
  const card = document.createElement("article");
  card.className = `article-card priority-${article.level}`;

  const content = document.createElement("div");
  const title = document.createElement("h3");
  const link = document.createElement("a");
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = article.title;
  title.append(link);

  const meta = document.createElement("div");
  meta.className = "article-meta";
  [article.journal, formatDate(article.publication_date), article.authors_display, `PMID ${article.pmid}`].forEach((value) => {
    const span = document.createElement("span");
    span.textContent = value;
    meta.append(span);
  });

  const tagRow = document.createElement("div");
  tagRow.className = "tag-row";
  (article.tags.length ? article.tags : [{ label: "ASD", kind: "topic" }]).slice(0, 8).forEach((tag) => {
    const pill = document.createElement("span");
    pill.className = `tag ${tag.kind || ""}`.trim();
    pill.textContent = tag.label;
    tagRow.append(pill);
  });

  const abstract = document.createElement("p");
  abstract.className = "abstract";
  abstract.textContent = article.abstract || article.abstract_excerpt || "Abstract not available from PubMed for this record.";

  const actions = document.createElement("div");
  actions.className = "article-actions";

  const openButton = document.createElement("a");
  openButton.className = "icon-button";
  openButton.href = article.url;
  openButton.target = "_blank";
  openButton.rel = "noreferrer";
  openButton.innerHTML = '<i data-lucide="external-link" aria-hidden="true"></i><span>Open</span>';

  const copyButton = document.createElement("button");
  copyButton.className = "icon-button";
  copyButton.type = "button";
  copyButton.innerHTML = '<i data-lucide="clipboard" aria-hidden="true"></i><span>Copy note</span>';
  copyButton.addEventListener("click", () => copyText(formatArticleNote(article), "Article note copied"));

  actions.append(openButton, copyButton);
  content.append(title, meta, tagRow, abstract, actions);

  const score = document.createElement("aside");
  score.className = "score-card";
  score.setAttribute("aria-label", `Impact score ${article.display_score}`);
  score.innerHTML = `
    <div class="score-number">${article.display_score}</div>
    <div>
      <div class="score-label">${priorityLabel(article.level)}</div>
      <div class="score-line">${article.reasons_summary}</div>
    </div>
  `;

  card.append(content, score);
  return card;
}

function updateMetrics(articles) {
  elements["metric-total"].textContent = String(articles.length);
  elements["metric-accepted"].textContent = String(articles.filter((article) => article.bucket === "accepted").length);
  elements["metric-watchlist"].textContent = String(articles.filter((article) => article.bucket === "watchlist").length);
  elements["metric-under25"].textContent = String(articles.filter((article) => article.is_under_25).length);
}

function updateDigest() {
  const digest = buildDigest();
  elements["digest-output"].value = digest;
  elements["digest-count"].textContent = `${state.filteredArticles.length} item${state.filteredArticles.length === 1 ? "" : "s"}`;
}

function buildDigest() {
  const sorted = [...state.filteredArticles].sort(sortArticles);
  const accepted = sorted.filter((article) => article.bucket === "accepted");
  const watch = sorted.filter((article) => article.bucket === "watchlist");
  const lines = [
    `# ASD Research Digest - ${formatDateForFile(new Date())}`,
    "",
    `Screened records in view: ${sorted.length}`,
    `Accepted records: ${accepted.length}`,
    `Watchlist records: ${watch.length}`,
    `Publication window filter: past ${elements["date-window"].value} days`,
    "",
    "## Accepted"
  ];

  lines.push(...formatDigestGroup(accepted));
  lines.push("", "## Watchlist");
  lines.push(...formatDigestGroup(watch.slice(0, 20)));
  lines.push("", "## Search");
  lines.push(data.run?.pubmed_url || "PubMed URL unavailable");

  return lines.join("\n");
}

function formatDigestGroup(group) {
  if (!group.length) return ["- None in the current queue."];
  return group.map((article) => {
    const tags = article.tags.map((tag) => tag.label).join(", ") || "ASD";
    return `- **${article.title}** (${article.journal}, ${formatDate(article.publication_date)}). Score ${article.display_score}. ${tags}. ${article.reasons_summary}. ${article.url}`;
  });
}

function formatArticleNote(article) {
  return [
    `Title: ${article.title}`,
    `Journal/date: ${article.journal}, ${formatDate(article.publication_date)}`,
    `Bucket: ${article.bucket_label}`,
    `Priority: ${priorityLabel(article.level)} (${article.display_score})`,
    `Signals: ${article.reasons_summary}`,
    `Study type: ${article.study_type_label}`,
    `PubMed: ${article.url}`,
    article.doi ? `DOI: ${article.doi}` : ""
  ].filter(Boolean).join("\n");
}

function exportCsv() {
  const header = ["score", "bucket", "study_type", "title", "journal", "date", "authors", "age_tags", "pmid", "doi", "url"];
  const rows = state.filteredArticles.map((article) => [
    article.display_score,
    article.bucket_label,
    article.study_type_label,
    article.title,
    article.journal,
    formatDate(article.publication_date),
    article.authors_display,
    article.age_labels.join("; "),
    article.pmid,
    article.doi,
    article.url
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `asd-research-radar-${formatDateForFile(new Date())}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function updateQueryPreview() {
  const lines = [
    data.run?.query || "Query unavailable",
    "",
    data.run?.pubmed_url || "PubMed URL unavailable",
    "",
    `Weekly command: ${data.run?.command || "python3 -m research_agent.cli run-weekly"}`
  ];
  elements["query-output"].textContent = lines.join("\n");
  renderJournalOutput();
}

function renderJournalOutput() {
  if (!elements["journal-output"]) return;
  const items = (data.journal_watchlist || []).map((journal) => {
    const item = document.createElement("li");
    item.innerHTML = `<strong>${journal.label}</strong><span>${journal.tier}</span>`;
    return item;
  });
  elements["journal-output"].replaceChildren(...items);
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === `${view}-view`);
  });
  updateDigest();
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    showToast(message);
  } catch (error) {
    console.error(error);
    showToast("Clipboard unavailable");
  }
}

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.append(toast);
  setTimeout(() => toast.remove(), 2400);
}

function withinDays(dateValue, days) {
  if (!dateValue) return false;
  const candidate = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(candidate.getTime())) return false;
  const now = data.generated_at_iso ? new Date(data.generated_at_iso) : new Date();
  const diff = Math.round((now - candidate) / 86400000);
  return diff <= days;
}

function compareDates(left, right) {
  const leftDate = new Date(`${left || "1900-01-01"}T00:00:00`).getTime();
  const rightDate = new Date(`${right || "1900-01-01"}T00:00:00`).getTime();
  return leftDate - rightDate;
}

function formatDate(value) {
  if (!value) return "Date unavailable";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

function formatDateForFile(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function priorityLabel(level) {
  if (level === "high") return "High priority";
  if (level === "watch") return "Watch";
  return "Background";
}

function csvEscape(value) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value || min));
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
