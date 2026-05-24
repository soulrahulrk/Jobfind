const state = {
  profile: {},
  sources: [],
  jobs: [],
};

const els = {
  profileLine: document.querySelector("#profileLine"),
  profileBox: document.querySelector("#profileBox"),
  source: document.querySelector("#source"),
  status: document.querySelector("#status"),
  q: document.querySelector("#q"),
  minScore: document.querySelector("#minScore"),
  scoreValue: document.querySelector("#scoreValue"),
  remote: document.querySelector("#remote"),
  salaryFloor: document.querySelector("#salaryFloor"),
  savedSearches: document.querySelector("#savedSearches"),
  jobs: document.querySelector("#jobs"),
  statusLine: document.querySelector("#statusLine"),
  jobCount: document.querySelector("#jobCount"),
  topScore: document.querySelector("#topScore"),
  appliedCount: document.querySelector("#appliedCount"),
  scanBtn: document.querySelector("#scanBtn"),
  reloadProfileBtn: document.querySelector("#reloadProfileBtn"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`${path}: ${error || `Request failed: ${response.status}`}`);
  }
  return response.json();
}

async function loadAll() {
  setStatus("Loading local profile and job data...");
  const [profile, sources] = await Promise.all([api("/api/profile"), api("/api/sources")]);
  state.profile = profile;
  state.sources = sources;
  renderProfile();
  renderSources();
  await loadJobs();
  setStatus("Ready.");
}

async function loadJobs() {
  const params = new URLSearchParams();
  if (els.q.value.trim()) params.set("q", els.q.value.trim());
  if (els.source.value) params.set("source", els.source.value);
  if (els.status.value) params.set("status", els.status.value);
  if (els.remote.checked) params.set("remote", "true");
  if (els.salaryFloor.checked) params.set("salary_floor", "true");
  params.set("min_score", els.minScore.value);
  state.jobs = await api(`/api/jobs?${params.toString()}`);
  renderJobs();
}

function renderProfile() {
  const p = state.profile;
  els.profileLine.textContent = `${p.name || "Rahul"} - ${p.location || "India"} - ${Array.isArray(p.skills) ? p.skills.slice(0, 4).join(", ") : "AI/ML, Python"}`;
  const rows = [
    ["Email", p.email],
    ["GitHub", p.github],
    ["LinkedIn", p.linkedin],
    ["LeetCode", p.leetcode],
    ["Salary floor", `INR ${p.salary_floor_inr_monthly || 10000}/month`],
  ];
  els.profileBox.innerHTML = rows
    .filter(([, value]) => value)
    .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${linkify(value)}</dd></div>`)
    .join("");
}

function renderSources() {
  const jobSources = state.sources.filter((source) => source.kind !== "saved_search");
  els.source.innerHTML = `<option value="">All sources</option>${jobSources
    .map((source) => `<option value="${escapeAttr(source.name)}">${escapeHtml(source.name)}</option>`)
    .join("")}`;

  const searches = state.sources.filter((source) => source.kind === "saved_search" && source.url);
  els.savedSearches.innerHTML = searches
    .map((source) => `<a href="${escapeAttr(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.name)}</a>`)
    .join("");
}

function renderJobs() {
  const jobs = state.jobs;
  els.jobCount.textContent = jobs.length;
  els.topScore.textContent = jobs.length ? jobs[0].match_score : 0;
  els.appliedCount.textContent = jobs.filter((job) => job.status === "applied").length;

  if (!jobs.length) {
    els.jobs.innerHTML = `<div class="empty">No matching jobs yet. Run a scan or open a saved search.</div>`;
    return;
  }

  els.jobs.innerHTML = jobs.map(renderJob).join("");
  document.querySelectorAll("[data-status]").forEach((select) => {
    select.addEventListener("change", updateJobStatus);
  });
  document.querySelectorAll("[data-notes]").forEach((textarea) => {
    textarea.addEventListener("blur", updateJobStatus);
  });
}

function renderJob(job) {
  const salary = job.salary_text || formatSalary(job.salary_min, job.salary_max) || "Salary not listed";
  const reasons = (job.match_reasons || []).map((reason) => `<span class="reason">${escapeHtml(reason)}</span>`).join("");
  const apply = job.apply_url
    ? `<a href="${escapeAttr(job.apply_url)}" target="_blank" rel="noreferrer">Open link</a>`
    : `<button type="button" disabled>No link</button>`;
  return `
    <article class="job">
      <div>
        <h3>${escapeHtml(job.title)}</h3>
        <div class="meta">
          <span>${escapeHtml(job.company || "Company not listed")}</span>
          <span>${escapeHtml(job.location || "Location not listed")}</span>
          <span>${escapeHtml(job.source)}</span>
          <span>${escapeHtml(salary)}</span>
          ${job.remote ? "<span>Remote</span>" : ""}
        </div>
        <div class="reasons">${reasons}</div>
        <p class="raw">${escapeHtml(job.raw_text || "")}</p>
      </div>
      <div class="job-side">
        <div class="score">
          <strong>${job.match_score}</strong>
          <div class="bar"><span style="width:${job.match_score}%"></span></div>
        </div>
        ${apply}
        <div class="status-row">
          <select data-status="${job.id}" aria-label="Status for ${escapeAttr(job.title)}">
            ${["new", "saved", "applied", "interview", "offer", "rejected"]
              .map((status) => `<option value="${status}" ${job.status === status ? "selected" : ""}>${titleCase(status)}</option>`)
              .join("")}
          </select>
          <textarea class="notes" data-notes="${job.id}" placeholder="Notes">${escapeHtml(job.notes || "")}</textarea>
        </div>
      </div>
    </article>
  `;
}

async function runScan() {
  els.scanBtn.disabled = true;
  setStatus("Scanning APIs and optional Gmail alerts...");
  try {
    const result = await api("/api/scan", { method: "POST" });
    const message = result.errors && result.errors.length
      ? `Stored ${result.stored} jobs. Some sources failed: ${result.errors.join("; ")}`
      : `Stored ${result.stored} jobs.`;
    setStatus(message);
    await loadJobs();
  } catch (error) {
    setStatus(`Scan failed: ${error.message}`);
  } finally {
    els.scanBtn.disabled = false;
  }
}

async function reloadProfile() {
  els.reloadProfileBtn.disabled = true;
  setStatus("Reloading resume PDF...");
  try {
    state.profile = await api("/api/profile/reload", { method: "POST" });
    renderProfile();
    setStatus("Profile reloaded from PDF.");
  } catch (error) {
    setStatus(`Profile reload failed: ${error.message}`);
  } finally {
    els.reloadProfileBtn.disabled = false;
  }
}

async function updateJobStatus(event) {
  const id = event.target.dataset.status || event.target.dataset.notes;
  const article = event.target.closest(".job");
  const status = article.querySelector("[data-status]").value;
  const notes = article.querySelector("[data-notes]").value;
  try {
    await api(`/api/jobs/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status, notes }),
    });
    setStatus("Status saved.");
    await loadJobs();
  } catch (error) {
    setStatus(`Could not save status: ${error.message}`);
  }
}

function setStatus(message) {
  els.statusLine.textContent = message;
}

function formatSalary(min, max) {
  if (!min && !max) return "";
  if (min && max && min !== max) return `INR ${min} - ${max}`;
  return `INR ${min || max}`;
}

function titleCase(value) {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function linkify(value) {
  const text = String(value);
  if (text.startsWith("http")) {
    return `<a href="${escapeAttr(text)}" target="_blank" rel="noreferrer">${escapeHtml(text)}</a>`;
  }
  if (text.includes("@")) {
    return `<a href="mailto:${escapeAttr(text)}">${escapeHtml(text)}</a>`;
  }
  return escapeHtml(text);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

let filterTimer;
function queueLoadJobs() {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(loadJobs, 150);
}

["input", "change"].forEach((eventName) => {
  [els.q, els.source, els.status, els.remote, els.salaryFloor].forEach((element) => {
    element.addEventListener(eventName, queueLoadJobs);
  });
});

els.minScore.addEventListener("input", () => {
  els.scoreValue.textContent = els.minScore.value;
  queueLoadJobs();
});
els.scanBtn.addEventListener("click", runScan);
els.reloadProfileBtn.addEventListener("click", reloadProfile);

loadAll().catch((error) => setStatus(`Startup failed: ${error.message}`));
