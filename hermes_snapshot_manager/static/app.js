(() => {
  const progressCard = document.getElementById("operation-progress");
  if (!progressCard) return;

  const kindEl = document.getElementById("operation-progress-kind");
  const barEl = document.getElementById("operation-progress-bar");
  const percentEl = document.getElementById("operation-progress-percent");
  const messageEl = document.getElementById("operation-progress-message");
  const detailEl = document.getElementById("operation-progress-detail");
  const errorEl = document.getElementById("operation-progress-error");
  const actionEl = document.getElementById("operation-progress-action");
  let pollTimer = null;

  function toneForStatus(status) {
    if (status === "completed") return "success";
    if (status === "failed") return "danger";
    if (status === "running") return "running";
    if (status === "stale") return "stale";
    return "neutral";
  }

  function renderState(state) {
    const hasState = state && Object.keys(state).length > 0;
    if (!hasState) {
      progressCard.classList.add("hidden");
      return;
    }

    progressCard.classList.remove("hidden");
    const progress = Number(state.progress || 0);
    const status = state.status || "idle";
    kindEl.textContent = `${state.kind || "operation"} · ${status}`;
    kindEl.className = status === "stale" ? "pill stale" : `pill pill-${toneForStatus(status)}`;
    barEl.classList.remove("running", "completed", "failed", "stale");
    if (["running", "completed", "failed", "stale"].includes(status)) barEl.classList.add(status);
    barEl.style.width = `${progress}%`;
    percentEl.textContent = `${progress}%`;
    messageEl.textContent = state.message || "Working…";
    const skippedSummary = Number(state.skipped_files_count || 0) > 0 ? `Skipped files: ${state.skipped_files_count}` : "";
    detailEl.textContent = [state.current_item || state.detail || "", skippedSummary].filter(Boolean).join(" · ");
    errorEl.textContent = state.error || "";

    if (actionEl) {
      actionEl.innerHTML = "";
      if (status === "stale") {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "btn-retry";
        retryBtn.textContent = "Resume / Retry";
        retryBtn.addEventListener("click", async () => {
          await fetch("/api/operations/current/clear", { method: "POST" });
          await fetchCurrentOperation();
        });
        actionEl.appendChild(retryBtn);
      } else if (status === "running") {
        const abortBtn = document.createElement("button");
        abortBtn.type = "button";
        abortBtn.className = "btn-abort";
        abortBtn.textContent = "Abort";
        abortBtn.addEventListener("click", async () => {
          await fetch("/api/operations/current/abort", { method: "POST" });
          await fetchCurrentOperation();
        });
        actionEl.appendChild(abortBtn);
      }
    }
  }

  async function fetchCurrentOperation() {
    try {
      const response = await fetch("/api/operations/current", { cache: "no-store" });
      renderState(await response.json());
    } catch (error) {
      errorEl.textContent = `Connection error: ${error.message}`;
      progressCard.classList.remove("hidden");
    }
  }

  function ensurePolling() {
    if (pollTimer !== null) return;
    pollTimer = window.setInterval(fetchCurrentOperation, 1000);
  }

  document.querySelectorAll(".js-operation-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      if (button) button.disabled = true;
      progressCard.classList.remove("hidden");
      messageEl.textContent = `Starting ${form.dataset.operationKind || "operation"}…`;
      detailEl.textContent = "";
      errorEl.textContent = "";
      try {
        const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || payload.detail || response.statusText);
        ensurePolling();
        await fetchCurrentOperation();
      } catch (error) {
        errorEl.textContent = String(error);
        if (button) button.disabled = false;
      }
    });
  });

  function setupScheduleForm() {
    const form = document.querySelector(".js-schedule-form");
    if (!form) return;

    const modeInputs = Array.from(form.querySelectorAll("input[name='schedule_mode']"));
    const everyHoursInput = form.querySelector("input[name='schedule_every_hours']");
    const dailyTimeInput = form.querySelector("input[name='schedule_daily_time']");
    const weeklyDayInput = form.querySelector("select[name='schedule_weekly_day']");
    const weeklyTimeInput = form.querySelector("input[name='schedule_weekly_time']");
    const customCronInput = form.querySelector("#schedule-cron-custom");
    const hiddenCronInput = form.querySelector("input[name='schedule_cron']");
    const preview = document.getElementById("schedule-cron-preview");
    const descriptionPreview = document.getElementById("schedule-description-preview");
    const panels = Array.from(form.querySelectorAll("[data-mode-panel]"));
    const currentCron = form.dataset.currentCron || hiddenCronInput?.value || "0 */6 * * *";

    function inferModeFromCron(cron) {
      const hourly = cron.match(/^0 \*\/(\d{1,2}) \* \* \*$/);
      if (hourly) return { mode: "every_hours", hours: hourly[1] };
      const daily = cron.match(/^([0-5]?\d) ([0-1]?\d|2[0-3]) \* \* \*$/);
      if (daily) return { mode: "daily", time: `${daily[2].padStart(2, "0")}:${daily[1].padStart(2, "0")}` };
      const weekly = cron.match(/^([0-5]?\d) ([0-1]?\d|2[0-3]) \* \* ([0-6])$/);
      if (weekly) return { mode: "weekly", day: weekly[3], time: `${weekly[2].padStart(2, "0")}:${weekly[1].padStart(2, "0")}` };
      return { mode: "custom" };
    }

    function describeCron(cron) {
      const hourly = cron.match(/^0 \*\/(\d{1,2}) \* \* \*$/);
      if (hourly) return `Every ${hourly[1]} hours`;
      const daily = cron.match(/^([0-5]?\d) ([0-1]?\d|2[0-3]) \* \* \*$/);
      if (daily) return `Daily at ${daily[2].padStart(2, "0")}:${daily[1].padStart(2, "0")} UTC`;
      const weekly = cron.match(/^([0-5]?\d) ([0-1]?\d|2[0-3]) \* \* ([0-6])$/);
      if (weekly) {
        const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        return `${weekdayNames[Number(weekly[3])]} at ${weekly[2].padStart(2, "0")}:${weekly[1].padStart(2, "0")} UTC`;
      }
      return "Custom cron schedule";
    }

    function selectedMode() {
      return modeInputs.find((input) => input.checked)?.value || "every_hours";
    }

    function computeCron(mode) {
      if (mode === "daily") {
        const [hour, minute] = (dailyTimeInput?.value || "03:00").split(":");
        return `${Number(minute)} ${Number(hour)} * * *`;
      }
      if (mode === "weekly") {
        const [hour, minute] = (weeklyTimeInput?.value || "08:00").split(":");
        return `${Number(minute)} ${Number(hour)} * * ${weeklyDayInput?.value || "1"}`;
      }
      if (mode === "custom") return (customCronInput?.value || currentCron).trim() || currentCron;
      const hours = Math.max(1, Math.min(24, Number(everyHoursInput?.value || 6)));
      return hours === 24 ? "0 0 * * *" : `0 */${hours} * * *`;
    }

    const inferred = inferModeFromCron(currentCron);
    modeInputs.forEach((input) => { input.checked = input.value === inferred.mode; });
    if (inferred.hours && everyHoursInput) everyHoursInput.value = inferred.hours;
    if (inferred.time && dailyTimeInput && inferred.mode === "daily") dailyTimeInput.value = inferred.time;
    if (inferred.day && weeklyDayInput) weeklyDayInput.value = inferred.day;
    if (inferred.time && weeklyTimeInput && inferred.mode === "weekly") weeklyTimeInput.value = inferred.time;
    if (customCronInput) customCronInput.value = currentCron;

    function renderMode() {
      const mode = selectedMode();
      panels.forEach((panel) => panel.classList.toggle("hidden", panel.dataset.modePanel !== mode));
      const cron = computeCron(mode);
      if (hiddenCronInput) hiddenCronInput.value = cron;
      if (preview) preview.innerHTML = `<code>${cron}</code>`;
      if (descriptionPreview) descriptionPreview.textContent = describeCron(cron);
    }

    modeInputs.forEach((input) => input.addEventListener("change", renderMode));
    everyHoursInput?.addEventListener("input", renderMode);
    dailyTimeInput?.addEventListener("input", renderMode);
    weeklyDayInput?.addEventListener("change", renderMode);
    weeklyTimeInput?.addEventListener("input", renderMode);
    customCronInput?.addEventListener("input", renderMode);
    renderMode();
  }

  function setupSnapshotTable() {
    const table = document.getElementById("snapshots-table");
    const filterInput = document.getElementById("snapshot-filter");
    const sortSelect = document.getElementById("snapshot-sort");
    if (!table || !filterInput || !sortSelect) return;
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr[data-filter-text]"));

    function applyTableState() {
      const query = filterInput.value.trim().toLowerCase();
      const sortMode = sortSelect.value;
      const visibleRows = rows.filter((row) => row.dataset.filterText.toLowerCase().includes(query));
      visibleRows.sort((a, b) => {
        const createdA = Date.parse(a.dataset.created || "") || 0;
        const createdB = Date.parse(b.dataset.created || "") || 0;
        const sizeA = Number(a.dataset.size || 0);
        const sizeB = Number(b.dataset.size || 0);
        if (sortMode === "created_asc") return createdA - createdB;
        if (sortMode === "size_desc") return sizeB - sizeA;
        if (sortMode === "size_asc") return sizeA - sizeB;
        return createdB - createdA;
      });
      rows.forEach((row) => row.remove());
      visibleRows.forEach((row) => tbody.appendChild(row));
      rows.forEach((row) => { row.classList.toggle("hidden", !visibleRows.includes(row)); });
    }

    filterInput.addEventListener("input", applyTableState);
    sortSelect.addEventListener("change", applyTableState);
    applyTableState();
  }

  setupScheduleForm();
  setupSnapshotTable();
  fetchCurrentOperation();
  ensurePolling();
})();
