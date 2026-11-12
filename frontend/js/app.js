import { apiRequest, postJson } from "./api.js";

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const app = { page: "dashboard", offset: 0, limit: 50, filter: "all", pollTimer: null, jobId: null, instructions: [] };
const pageNames = { dashboard: "Dashboard", run: "Run verification", coverage: "Coverage", results: "Test results", instructions: "Instruction set", reports: "Reports", about: "About" };

function number(value) { return Number(value || 0).toLocaleString(); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
function showToast(message, success = false) {
  const toast = $("#toast"); toast.textContent = message; toast.classList.toggle("success", success); toast.classList.add("show");
  window.clearTimeout(showToast.timer); showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3800);
}
function showError(error) { showToast(error?.message || "The request could not be completed."); }

function navigate() {
  const requested = location.hash.slice(1) || "dashboard";
  app.page = pageNames[requested] ? requested : "dashboard";
  $$(".page").forEach((page) => page.classList.toggle("active", page.id === `page-${app.page}`));
  $$(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.page === app.page));
  $("#current-section").textContent = pageNames[app.page];
  $("#sidebar").classList.remove("open");
  if (app.page === "dashboard") refreshDashboard();
  if (app.page === "coverage") refreshCoverage();
  if (app.page === "results") refreshResults();
  if (app.page === "instructions") loadInstructions();
  if (app.page === "reports") refreshReport();
}

async function checkHealth() {
  const dot = $("#service-dot"), label = $("#service-label");
  try { await apiRequest("/health"); dot.className = "service-dot online"; label.textContent = "API connected"; }
  catch { dot.className = "service-dot offline"; label.textContent = "API unavailable"; }
}

async function refreshDashboard() {
  try {
    const data = await apiRequest("/summary");
    const summary = data.summary;
    if (!summary) {
      ["#stat-tests", "#stat-passed", "#stat-failed", "#stat-instructions", "#stat-coverage", "#stat-pass-rate"].forEach((id) => { $(id).textContent = "—"; });
      $("#last-seed").textContent = "—"; $("#last-time").textContent = "—"; $("#legend-passed").textContent = "—"; $("#legend-failed").textContent = "—"; $("#coverage-count").textContent = "— / —"; $("#donut-rate").textContent = "—"; $("#ring-value").textContent = "—";
      setDonut("#outcome-donut", 0, "var(--green)"); setDonut("#coverage-ring", 0, "var(--blue)"); renderRecent([]);
      if (data.job_id && ["starting", "running"].includes(data.status)) {
        app.jobId = data.job_id; $("#run-placeholder").classList.add("hidden"); $("#progress-content").classList.remove("hidden");
        $("#run-seed").textContent = data.last_seed; setProgress(data.progress.completed, data.progress.total); setRunStatus(data.status); pollJob(data.job_id);
      }
      return;
    }
    const cov = summary.coverage, passRate = summary.tests_run ? 100 * summary.passed / summary.tests_run : 0;
    $("#stat-tests").textContent = number(summary.tests_run); $("#stat-passed").textContent = number(summary.passed); $("#stat-failed").textContent = number(summary.failed);
    $("#stat-instructions").textContent = number(summary.total_instructions_executed); $("#stat-coverage").textContent = `${cov.covered_instructions} / ${cov.supported_instructions}`;
    $("#stat-pass-rate").textContent = `${passRate.toFixed(1)}%`; $("#stat-tests-note").textContent = `${number(summary.tests_requested)} requested`;
    $("#stat-pass-note").textContent = `${passRate.toFixed(1)}% of executed programs`; $("#stat-fail-note").textContent = summary.failed ? "Review mismatches below" : "No architectural mismatches";
    $("#stat-coverage-note").textContent = `${cov.instruction_coverage_percent.toFixed(1)}% mnemonic coverage`; $("#stat-run-time").textContent = `${summary.elapsed_seconds.toFixed(3)} s execution time`;
    $("#last-seed").textContent = data.last_seed; $("#last-time").textContent = formatDate(data.timestamp); $("#legend-passed").textContent = number(summary.passed); $("#legend-failed").textContent = number(summary.failed);
    $("#donut-rate").textContent = `${passRate.toFixed(0)}%`; $("#coverage-count").textContent = `${cov.covered_instructions} / ${cov.supported_instructions}`; $("#ring-value").textContent = `${cov.instruction_coverage_percent.toFixed(0)}%`;
    setDonut("#outcome-donut", passRate, "var(--green)"); setDonut("#coverage-ring", cov.instruction_coverage_percent, "var(--blue)");
    if (data.status === "running" || data.status === "starting") { app.jobId = data.job_id; pollJob(data.job_id); }
    const recent = await apiRequest("/results?offset=0&limit=6"); renderRecent(recent.results);
  } catch (error) { if (!String(error.message).includes("Run verification")) showError(error); }
}

function setDonut(selector, percentage, color) { $(selector).style.background = `conic-gradient(${color} 0 ${Math.max(0, Math.min(100, percentage)) * 3.6}deg, #25303c ${Math.max(0, Math.min(100, percentage)) * 3.6}deg 360deg)`; }
function formatDate(value) { if (!value) return "—"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); }
function statusMarkup(status) { return `<span class="status-pill ${status === "PASS" ? "pass" : "fail"}">${escapeHtml(status)}</span>`; }
function renderRecent(rows) {
  const body = $("#recent-results");
  if (!rows?.length) { body.innerHTML = '<tr><td colspan="5" class="empty-cell">Run a verification to populate results.</td></tr>'; $("#execution-chart").innerHTML = '<span class="empty-profile">Run verification to plot executed instructions.</span>'; return; }
  body.innerHTML = rows.map((row) => `<tr><td class="mono">${row.test_id}</td><td class="mono">${number(row.instructions_executed)}</td><td>${statusMarkup(row.status)}</td><td class="mono">${row.execution_seconds.toFixed(4)}s</td><td><button class="view-button" data-detail="${row.test_id}">Inspect</button></td></tr>`).join("");
  const max = Math.max(...rows.map((row) => row.instructions_executed), 1);
  $("#execution-chart").innerHTML = rows.map((row) => `<div class="execution-column" title="Test ${row.test_id}: ${row.instructions_executed} instructions"><span style="height:${Math.max(5, row.instructions_executed / max * 100)}%"></span><small>#${row.test_id}</small></div>`).join("");
  $$('[data-detail]', body).forEach((button) => button.addEventListener("click", () => openResult(Number(button.dataset.detail))));
}

async function refreshCoverage() {
  try {
    const data = await apiRequest("/coverage");
    $("#coverage-run-status").textContent = data.status === "completed" ? "LATEST RUN" : data.status.toUpperCase();
    const counts = data.occurrence_counts || {}, all = app.instructions.length ? app.instructions : (await apiRequest("/instructions")).instructions;
    app.instructions = all;
    const covered = data.covered_instructions ?? 0, total = data.supported_instructions ?? all.length, percent = data.instruction_coverage_percent ?? 0;
    $("#coverage-page-percent").textContent = `${percent.toFixed(1)}%`; $("#coverage-page-count").textContent = `${covered} / ${total} instructions`;
    $("#coverage-total-executions").textContent = number(Object.values(counts).reduce((sum, value) => sum + value, 0)); setDonut("#coverage-page-ring", percent, "var(--blue)");
    $("#coverage-cards").innerHTML = all.map((item) => { const hits = counts[item.mnemonic] || 0; const ratio = hits ? 100 : 0; return `<article class="coverage-item"><div class="coverage-item-top"><strong>${escapeHtml(item.mnemonic)}</strong><span>${hits ? "COVERED" : "NOT SEEN"}</span></div><div class="bar-track"><span style="width:${ratio}%"></span></div><small>${number(hits)} executed occurrences</small></article>`; }).join("");
    $("#category-coverage").innerHTML = Object.entries(data.categories || {}).map(([name, value]) => `<div class="category-row"><span>${escapeHtml(name)}</span><div class="bar-track"><span style="width:${value.total ? value.covered / value.total * 100 : 0}%"></span></div><strong>${value.covered} / ${value.total}</strong></div>`).join("");
    const memory = data.memory || {}; const metrics = [["Loads", memory.loads || 0], ["Stores", memory.stores || 0], ["Unique addresses", memory.unique_addresses || 0], ["Aligned accesses", memory.aligned_accesses || 0]];
    $("#memory-coverage").innerHTML = metrics.map(([name, value]) => `<div class="memory-metric"><strong>${number(value)}</strong><small>${name}</small></div>`).join("");
  } catch (error) { showError(error); }
}

async function refreshResults() {
  try {
    const params = new URLSearchParams({ offset: String(app.offset), limit: String(app.limit), status: app.filter });
    const data = await apiRequest(`/results?${params}`); const summary = await apiRequest("/summary");
    $("#results-seed").textContent = `SEED ${summary.last_seed ?? "—"}`; $("#results-count").textContent = `${number(data.total)} ${app.filter === "all" ? "tests" : app.filter.toLowerCase() + " tests"} · page ${Math.floor(app.offset / app.limit) + 1}`;
    const body = $("#results-body");
    if (!data.results.length) body.innerHTML = '<tr><td colspan="7" class="empty-cell">No results match this view.</td></tr>';
    else body.innerHTML = data.results.map((row) => `<tr><td class="mono">${row.test_id}</td><td class="mono">${row.seed}</td><td class="mono">${row.instructions_executed}</td><td>${statusMarkup(row.status)}</td><td title="${escapeHtml(row.mismatch_summary || "No mismatch")}">${escapeHtml(row.mismatch_summary || "—")}</td><td class="mono">${row.execution_seconds.toFixed(4)}s</td><td><button class="view-button" data-detail="${row.test_id}">View details</button></td></tr>`).join("");
    $$('[data-detail]', body).forEach((button) => button.addEventListener("click", () => openResult(Number(button.dataset.detail))));
    const start = data.total ? app.offset + 1 : 0, end = Math.min(app.offset + app.limit, data.total); $("#page-indicator").textContent = `${start}–${end} of ${number(data.total)}`;
    $("#prev-page").disabled = app.offset === 0; $("#next-page").disabled = app.offset + app.limit >= data.total;
  } catch (error) { $("#results-count").textContent = "No verification results available."; $("#results-body").innerHTML = '<tr><td colspan="7" class="empty-cell">Run verification to see test results.</td></tr>'; }
}

async function loadInstructions() {
  if (!app.instructions.length) { try { app.instructions = (await apiRequest("/instructions")).instructions; } catch (error) { showError(error); return; } }
  $("#isa-total").textContent = app.instructions.length; renderInstructions("all");
}
function renderInstructions(category) {
  const entries = category === "all" ? app.instructions : app.instructions.filter((item) => item.category === category);
  $("#instruction-grid").innerHTML = entries.map((item) => `<article class="instruction-card"><div class="instruction-card-top"><code>${escapeHtml(item.mnemonic)}</code><span class="category-tag">${escapeHtml(item.category)}</span></div><p>${escapeHtml(item.description)}</p></article>`).join("");
}

async function refreshReport() {
  try {
    const data = await apiRequest("/report"); const summary = data.summary;
    if (!summary) throw new Error("The report is still being generated.");
    $("#report-title").textContent = `Verification run · seed ${data.seed}`; $("#report-description").textContent = `${number(summary.tests_run)} tests completed at ${formatDate(data.generated_at)}.`;
    $("#report-meta").textContent = `PASS ${summary.passed}  ·  FAIL ${summary.failed}  ·  ${summary.coverage.instruction_coverage_percent.toFixed(1)}% mnemonic coverage  ·  ${summary.elapsed_seconds.toFixed(3)}s`;
    $("#report-preview").textContent = JSON.stringify({ generated_at: data.generated_at, seed: data.seed, ...summary }, null, 2);
    const link = $("#download-report"); link.href = data.download_url; link.classList.remove("disabled"); link.removeAttribute("aria-disabled");
  } catch (error) { $("#report-title").textContent = "No report generated yet"; $("#report-description").textContent = error.message; $("#report-preview").textContent = "No report data available."; }
}

async function startRun(event) {
  event.preventDefault(); const form = new FormData(event.currentTarget); const tests = Number(form.get("tests"));
  const payload = { tests, coverage_guided: form.has("coverage_guided"), min_length: Number(form.get("min_length")), max_length: Number(form.get("max_length")) };
  if (String(form.get("seed")).trim() !== "") payload.seed = Number(form.get("seed"));
  if (payload.min_length > payload.max_length) { showToast("Minimum program length must not exceed maximum length."); return; }
  const button = $("#run-submit"); button.disabled = true; $("#run-placeholder").classList.add("hidden"); $("#progress-content").classList.remove("hidden"); setRunStatus("starting"); setProgress(0, tests); $("#run-message").textContent = "Starting verification…";
  try {
    const job = await postJson("/run", payload); app.jobId = job.job_id; $("#run-seed").textContent = job.seed; $("#run-job-id").textContent = job.job_id.slice(0, 12); setRunStatus("running"); $("#run-message").textContent = "Running the verification engine…"; pollJob(job.job_id);
  } catch (error) { button.disabled = false; setRunStatus("failed"); $("#run-message").textContent = error.message; showError(error); }
}

function setRunStatus(status) { const badge = $("#run-status"); badge.textContent = status.toUpperCase(); badge.className = `status-badge ${status}`; }
function setProgress(completed, total) { const percentage = total ? completed / total * 100 : 0; $("#progress-count").textContent = `${number(completed)} / ${number(total)}`; $("#progress-percent").textContent = `${percentage.toFixed(1)}%`; $("#progress-bar").style.width = `${percentage}%`; }
async function pollJob(jobId) {
  window.clearTimeout(app.pollTimer);
  try {
    const job = await apiRequest(`/jobs/${encodeURIComponent(jobId)}`); setProgress(job.progress.completed, job.progress.total);
    $("#run-seed").textContent = job.seed; setRunStatus(job.status); $("#run-message").textContent = job.status === "completed" ? "Verification completed successfully." : job.status === "failed" ? (job.error?.message || "Verification failed.") : "Running the verification engine…";
    const active = job.status === "running" || job.status === "starting"; $("#run-submit").disabled = active;
    if (active) app.pollTimer = window.setTimeout(() => pollJob(jobId), 450);
    else {
      $("#view-run-results").classList.remove("hidden"); await refreshDashboard(); await refreshCoverage(); await refreshResults(); await refreshReport();
      if (job.status === "completed") showToast(`Verification finished: ${number(job.summary.passed)} passed, ${number(job.summary.failed)} failed.`, true);
    }
  } catch (error) { $("#run-submit").disabled = false; $("#run-message").textContent = error.message; setRunStatus("failed"); showError(error); }
}

async function openResult(testId) {
  const dialog = $("#detail-dialog"), content = $("#detail-content"); $("#detail-title").textContent = `Test ${testId}`; content.innerHTML = '<div class="loading-card">Replaying the stored instruction program against both models…</div>'; dialog.showModal();
  try { renderDetails(await apiRequest(`/results/${testId}`)); } catch (error) { content.textContent = error.message; }
}
function renderDetails(data) {
  const content = $("#detail-content"); const mismatches = data.mismatches || []; const outcome = data.status || (mismatches.length ? "FAIL" : "PASS");
  const mismatchHtml = mismatches.length ? mismatches.map((item) => `<div><b>${escapeHtml(item.kind)} ${escapeHtml(item.location)}</b> · expected <code>${escapeHtml(item.expected)}</code> · actual <code>${escapeHtml(item.actual)}</code></div>`).join("") : "No architectural mismatch was detected.";
  const stateHtml = (label, state) => `<section class="state-section"><h3>${label} STATE</h3><div class="pc-line">PC&nbsp; 0x${Number(state.pc).toString(16).padStart(8, "0")}</div><div class="register-grid">${state.registers.map((value, index) => `<div class="register-cell"><b>x${index}</b> ${Number(value).toString(16).padStart(8, "0")}</div>`).join("")}</div><div class="memory-block"><b>Non-zero memory words</b><br>${Object.keys(state.memory.nonzero_words).length ? Object.entries(state.memory.nonzero_words).map(([address, value]) => `${address}: 0x${Number(value).toString(16).padStart(8, "0")}`).join("<br>") : "(empty)"}</div></section>`;
  content.innerHTML = `<div class="detail-status">${statusMarkup(outcome)}<span class="mono">seed ${escapeHtml(data.seed)} · ${data.executed_program?.length || 0} instructions executed</span></div>${data.instruction_causing_failure ? `<div class="detail-mismatch"><b>Instruction associated with mismatch</b><br><code>${escapeHtml(data.instruction_causing_failure)}</code></div>` : ""}<div class="detail-mismatch ${mismatches.length ? "" : "pass-detail"}"><b>${mismatches.length ? "Mismatch details" : "Architectural state matched"}</b><br>${mismatchHtml}</div><div class="detail-program"><h3>GENERATED PROGRAM</h3><pre>${data.program.map((instruction, index) => `${String(index).padStart(3, "0")}  ${escapeHtml(instruction)}`).join("\n")}</pre></div><div class="state-grid">${stateHtml("Expected", data.expected)}${stateHtml("Actual", data.actual)}</div>`;
}

async function replayTest(event) {
  event.preventDefault(); const values = new FormData(event.currentTarget); const output = $("#replay-result"); output.classList.remove("hidden"); output.textContent = "Replaying test against the verification engine…";
  try {
    const minLength = Number(values.get("min_length")), maxLength = Number(values.get("max_length"));
    if (minLength > maxLength) throw new Error("Minimum program length must not exceed maximum length.");
    const data = await postJson("/replay", { seed: Number(values.get("seed")), test_id: Number(values.get("test_id")), min_length: minLength, max_length: maxLength, coverage_guided: values.has("coverage_guided") });
    output.innerHTML = `<div>${statusMarkup(data.status)} <span class="mono">seed ${data.seed} · test ${data.test_id}</span> <button class="view-button" id="replay-open-detail">Open architectural details →</button></div><pre>${data.program.map((instruction, index) => `${String(index).padStart(3, "0")}  ${escapeHtml(instruction)}`).join("\n")}</pre>`;
    $("#replay-open-detail").addEventListener("click", () => { $("#detail-title").textContent = `Replay · test ${data.test_id}`; renderDetails(data); $("#detail-dialog").showModal(); });
    showToast(`Test ${data.test_id} replayed: ${data.status}.`, data.status === "PASS");
  } catch (error) { output.textContent = error.message; showError(error); }
}

function wireEvents() {
  window.addEventListener("hashchange", navigate);
  $("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#refresh-button").addEventListener("click", () => { refreshDashboard(); checkHealth(); showToast("Dashboard refreshed.", true); });
  $("#run-form").addEventListener("submit", startRun);
  $("#replay-form").addEventListener("submit", replayTest);
  $("#close-dialog").addEventListener("click", () => $("#detail-dialog").close());
  $("#detail-dialog").addEventListener("click", (event) => { if (event.target === $("#detail-dialog")) $("#detail-dialog").close(); });
  $("#result-filter").addEventListener("change", (event) => { app.filter = event.target.value; app.offset = 0; refreshResults(); });
  $("#results-refresh").addEventListener("click", refreshResults);
  $("#prev-page").addEventListener("click", () => { app.offset = Math.max(0, app.offset - app.limit); refreshResults(); });
  $("#next-page").addEventListener("click", () => { app.offset += app.limit; refreshResults(); });
  $("#instruction-filters").addEventListener("click", (event) => { const button = event.target.closest("[data-category]"); if (!button) return; $$(".filter-tab").forEach((item) => item.classList.toggle("selected", item === button)); renderInstructions(button.dataset.category); });
}

wireEvents(); navigate(); checkHealth();
