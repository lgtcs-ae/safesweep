(function () {
  "use strict";

  const page = document.body.dataset.page;
  const ACTIVE_SCAN_JOB_KEY = "safesweep.activeScanJobId";

  function text(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function formatBytes(value) {
    let size = Number(value || 0);
    const units = ["B", "KB", "MB", "GB", "TB"];
    for (const unit of units) {
      if (size < 1024 || unit === "TB") {
        return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
      }
      size /= 1024;
    }
    return "0 B";
  }

  function formatCount(value) {
    return Number(value || 0).toLocaleString("en-US");
  }

  function shortPath(value) {
    const path = String(value || "");
    return path.replace(/^\/Users\/[^/]+/, "~");
  }

  function compactPath(value, maxSegments = 4) {
    const path = String(value || "").trim();
    if (!path) {
      return "";
    }
    if (path.length <= 90) {
      return path;
    }
    const segments = path.split("/").filter(Boolean);
    if (segments.length <= maxSegments) {
      return path;
    }
    return `…/${segments.slice(-maxSegments).join("/")}`;
  }

  function formatDateTime(value) {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    const now = new Date();
    const sameDay =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate();
    const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    return sameDay ? `Today, ${time}` : `${date.toLocaleDateString()} ${time}`;
  }

  function extensionLabel(record) {
    const extension = String((record && record.extension) || "").replace(".", "");
    if (extension) {
      return extension.slice(0, 5);
    }
    const name = String((record && record.name) || "");
    const suffix = name.includes(".") ? name.split(".").pop() : "file";
    return suffix.slice(0, 5);
  }

  function splitLines(value) {
    return value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function getJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || payload.error || "Request failed.");
    }
    return payload;
  }

  function defaultFolders() {
    try {
      return JSON.parse(document.body.dataset.defaultFolders || "[]");
    } catch (_error) {
      return [];
    }
  }

  function renderExtensions(items) {
    const container = document.getElementById("extension-list");
    if (!container) {
      return;
    }
    if (!items || items.length === 0) {
      container.innerHTML =
        '<div class="rounded-lg border border-dashed border-[#cfdbe2] p-4 text-sm text-[#657382]">Run a scan to see file type counts.</div>';
      return;
    }
    const maxCount = Math.max.apply(
      null,
      items.map((item) => item.count)
    );
    container.innerHTML = items
      .map((item) => {
        const width = Math.max(8, Math.round((item.count / maxCount) * 100));
        return `
          <div>
            <div class="flex items-center justify-between text-sm">
              <span class="font-semibold text-[#243445]">${escapeHtml(item.extension)}</span>
              <span class="text-[#657382]">${item.count}</span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-[#edf2f4]">
              <div class="h-full rounded-full bg-[#1f9f78]" style="width: ${width}%"></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getActiveScanJobId() {
    try {
      return window.localStorage.getItem(ACTIVE_SCAN_JOB_KEY) || "";
    } catch (_error) {
      return "";
    }
  }

  function saveActiveScanJobId(jobId) {
    try {
      window.localStorage.setItem(ACTIVE_SCAN_JOB_KEY, jobId);
    } catch (_error) {
      // The scan still runs even if localStorage is unavailable.
    }
  }

  function clearActiveScanJobId(jobId) {
    try {
      const activeJobId = window.localStorage.getItem(ACTIVE_SCAN_JOB_KEY);
      if (!jobId || activeJobId === jobId) {
        window.localStorage.removeItem(ACTIVE_SCAN_JOB_KEY);
      }
    } catch (_error) {
      // Nothing to clear when storage is unavailable.
    }
  }

  async function loadDashboard() {
    const payload = await getJson("/api/dashboard");
    const totals = payload.totals || {};
    text("metric-files", String(totals.total_files || 0));
    text("metric-confirmed", String(totals.confirmed_duplicate_groups || 0));
    text("metric-likely", String(totals.likely_duplicate_groups || 0));
    text("metric-review-groups", String(totals.duplicate_group_count || 0));
    text("metric-vault", totals.estimated_vault_size || "0 B");
    text("metric-vault-size-label", totals.estimated_vault_size || "--");
    renderExtensions(payload.extensions || []);

    if (!payload.latest_scan) {
      text("latest-dashboard-summary", "No scan yet.");
      return;
    }
    const scan = payload.latest_scan;
    const completedAt = formatDateTime(scan.completed_at || "");
    text("latest-subtitle", completedAt || "Last scan complete");
    text("latest-review-folder", `${formatCount(scan.total_files || 0)} files scanned`);
    text(
      "latest-dashboard-summary",
      `${formatCount(scan.total_files || 0)} files scanned - ${formatBytes(scan.total_bytes || 0)} total - ${formatCount(scan.duplicate_group_count || 0)} groups`
    );
    const link = document.getElementById("dashboard-results-link");
    if (link) {
      link.href = `/results?scan_id=${encodeURIComponent(scan.scan_id)}`;
      link.classList.remove("hidden");
      link.classList.add("inline-flex");
    }
  }

  async function loadLatestScanSnapshot() {
    const payload = await getJson("/api/dashboard");
    const scan = payload.latest_scan;
    if (!scan) {
      return;
    }

    renderCompletedScan(scan);
    text("scan-status", `Last scan completed ${scan.completed_at || ""}`.trim());
    text("scan-status-detail", "You can review the latest results or start a new scan.");
  }

  function renderCompletedScan(scan) {
    text("summary-badge", "Complete");
    text("summary-files", String(scan.total_files || 0));
    text("summary-size", formatBytes(scan.total_bytes || 0));
    text("summary-skipped", String(scan.skipped_items || 0));
    text("summary-errors", String(scan.error_count || 0));
    text("summary-groups", String(scan.duplicate_group_count || 0));
    text("summary-hashed", String(scan.hashed_file_count || 0));
    text("summary-cleanup", String(scan.cleanup_candidate_count || 0));
    text("summary-folder", scan.review_folder || "No review folder.");
    renderClassifications(scan);
    renderScanErrors(scan);

    const link = document.getElementById("scan-results-link");
    if (link) {
      link.href = `/results?scan_id=${encodeURIComponent(scan.scan_id)}`;
      link.classList.remove("hidden");
      link.classList.add("inline-flex");
    }

    setScanProgress({
      status: "completed",
      files_scanned: scan.total_files || 0,
      files_hashed: scan.hashed_file_count || 0,
      current_path: scan.review_folder || "",
    });
  }

  function setupScanPage() {
    const foldersInput = document.getElementById("folders-input");
    const excludesInput = document.getElementById("excludes-input");
    const includeHidden = document.getElementById("include-hidden");
    const scanForm = document.getElementById("scan-form");
    const scanButton = document.getElementById("scan-button");
    const useDefaults = document.getElementById("use-defaults");
    let scanInFlight = false;

    const applyDefaults = () => {
      foldersInput.value = defaultFolders().join("\n");
    };

    applyDefaults();
    useDefaults.addEventListener("click", applyDefaults);
    setupPermissionModal();
    const activeJobId = getActiveScanJobId();
    if (activeJobId) {
      resumeActiveScanJob(activeJobId, scanButton).catch(() => {
        clearActiveScanJobId(activeJobId);
        loadLatestScanSnapshot().catch(() => {});
      });
    } else {
      loadLatestScanSnapshot().catch(() => {});
    }

    const selectFolder = document.getElementById("select-folder");
    if (selectFolder) {
      selectFolder.addEventListener("click", async () => {
        selectFolder.disabled = true;
        const originalText = selectFolder.textContent;
        selectFolder.textContent = "Selecting...";
        try {
          const payload = await getJson("/api/select-folder", { method: "POST" });
          const selected = String(payload.folder || "").trim();
          if (selected) {
            const existing = splitLines(foldersInput.value);
            if (!existing.includes(selected)) {
              existing.push(selected);
              foldersInput.value = existing.join("\n");
            }
            text("scan-status", `Selected folder: ${shortPath(selected)}`);
          }
        } catch (error) {
          text("scan-status", error.message);
        } finally {
          selectFolder.disabled = false;
          selectFolder.textContent = originalText;
        }
      });
    }

    const startScan = async () => {
      if (scanInFlight) {
        return;
      }
      scanInFlight = true;
      scanButton.disabled = true;
      scanButton.classList.add("scan-pulse");
      text("scan-status", "Scanning...");
      text("summary-badge", "Running");
      let startedJobId = "";
      setScanProgress({
        status: "running",
        files_scanned: 0,
        files_hashed: 0,
        current_path: "",
      });

      try {
        const payload = await getJson("/api/scan/start", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            folders: splitLines(foldersInput.value),
            excludes: splitLines(excludesInput.value),
            include_hidden: includeHidden.checked,
          }),
        });
        startedJobId = payload.job.job_id;
        saveActiveScanJobId(startedJobId);
        await pollScanJob(startedJobId);
      } catch (error) {
        if (!startedJobId) {
          clearActiveScanJobId();
        }
        text("scan-status", error.message);
        text("summary-badge", "Error");
        setScanProgress({
          status: "failed",
          files_scanned: 0,
          files_hashed: 0,
          current_path: "",
        });
      } finally {
        scanButton.disabled = false;
        scanButton.classList.remove("scan-pulse");
        scanInFlight = false;
      }
    };

    scanForm.addEventListener("submit", (event) => {
      event.preventDefault();
      startScan();
    });

    scanButton.addEventListener("click", (event) => {
      event.preventDefault();
      startScan();
    });
  }

  async function resumeActiveScanJob(jobId, scanButton) {
    if (scanButton) {
      scanButton.disabled = true;
      scanButton.classList.add("scan-pulse");
    }
    const payload = await getJson(`/api/scan/status/${encodeURIComponent(jobId)}`);
    const job = payload.job;

    if (job.status === "completed") {
      await renderScanJobResult(jobId);
      clearActiveScanJobId(jobId);
      if (scanButton) {
        scanButton.disabled = false;
        scanButton.classList.remove("scan-pulse");
      }
      return;
    }

    if (job.status === "failed" || job.status === "cancelled") {
      clearActiveScanJobId(jobId);
      text("summary-badge", labelForJobStatus(job.status));
      text("scan-status", job.error_message || labelForJobStatus(job.status));
      setScanProgress(job);
      if (scanButton) {
        scanButton.disabled = false;
        scanButton.classList.remove("scan-pulse");
      }
      return;
    }

    text("summary-badge", labelForJobStatus(job.status));
    text("scan-status", statusLine(job));
    setScanProgress(job);
    try {
      await pollScanJob(jobId);
    } finally {
      if (scanButton) {
        scanButton.disabled = false;
        scanButton.classList.remove("scan-pulse");
      }
    }
  }

  async function pollScanJob(jobId) {
    let done = false;
    while (!done) {
      await sleep(700);
      const payload = await getJson(`/api/scan/status/${encodeURIComponent(jobId)}`);
      const job = payload.job;
      text("summary-files", String(job.files_scanned || 0));
      text("summary-hashed", String(job.files_hashed || 0));
      text("summary-groups", String(job.groups_found || 0));
      text("summary-badge", labelForJobStatus(job.status));
      text("scan-status", statusLine(job));
      setScanProgress(job);

      if (job.status === "completed") {
        await renderScanJobResult(jobId);
        clearActiveScanJobId(jobId);
        text("scan-status", "Complete. No files were moved.");
        done = true;
      }

      if (job.status === "failed" || job.status === "cancelled") {
        clearActiveScanJobId(jobId);
        throw new Error(job.error_message || `Scan ${job.status}.`);
      }
    }
  }

  async function renderScanJobResult(jobId) {
    const resultPayload = await getJson(`/api/scan/result/${encodeURIComponent(jobId)}`);
    const scan = resultPayload.scan;
    if (!scan) {
      throw new Error("Scan result is not ready yet.");
    }
    renderCompletedScan(scan);
    return scan;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function labelForJobStatus(status) {
    return {
      queued: "Queued",
      running: "Running",
      completed: "Complete",
      failed: "Error",
      cancelled: "Cancelled",
    }[status] || status;
  }

  function statusLine(job) {
    if (job.status === "queued") {
      return "Queued...";
    }
    if (job.status === "running") {
      return `Scanning ${formatCount(job.files_scanned || 0)} files · ${formatCount(job.files_hashed || 0)} hashed`;
    }
    return labelForJobStatus(job.status);
  }

  function setScanProgress(job) {
    const title = document.getElementById("summary-progress-title");
    const subtitle = document.getElementById("summary-progress-subtitle");
    const path = document.getElementById("summary-progress-path");
    const bar = document.getElementById("summary-progress-bar");
    const orb = document.getElementById("summary-scan-orb");
    const counts = document.getElementById("summary-progress-counts");
    const detail = document.getElementById("summary-progress-detail");
    const footerIndicator = document.getElementById("scan-status-indicator");
    const footerStatus = document.getElementById("scan-status");
    const footerDetail = document.getElementById("scan-status-detail");
    if (!title || !subtitle || !path || !bar || !counts || !detail) {
      return;
    }

    const status = String(job.status || "");
    const filesScanned = Number(job.files_scanned || 0);
    const filesHashed = Number(job.files_hashed || 0);
    const currentPath = compactPath(job.current_path || "", 3);
    const currentLabel = currentPath ? `Current file: ${currentPath}` : "Waiting for the first file...";
    const setFooterState = (state) => {
      if (footerIndicator) {
        footerIndicator.classList.remove("is-running", "is-complete", "is-error");
        if (state === "running") {
          footerIndicator.classList.add("is-running");
        } else if (state === "completed") {
          footerIndicator.classList.add("is-complete");
        } else if (state === "failed") {
          footerIndicator.classList.add("is-error");
        }
      }
    };
    const setOrbState = (state) => {
      if (!orb) {
        return;
      }
      orb.classList.remove("is-running", "is-complete", "is-error");
      if (state === "running") {
        orb.classList.add("is-running");
      } else if (state === "completed") {
        orb.classList.add("is-complete");
      } else if (state === "failed") {
        orb.classList.add("is-error");
      }
    };

    if (status === "running") {
      title.textContent = "Scanning in progress";
      subtitle.textContent = `We have scanned ${formatCount(filesScanned)} files and hashed ${formatCount(filesHashed)} so far.`;
      path.textContent = currentLabel;
      bar.classList.add("is-running");
      bar.classList.remove("is-complete");
      counts.textContent = `${formatCount(filesScanned)} files scanned`;
      detail.textContent = `${formatCount(filesHashed)} hashed`;
      if (footerStatus) {
        footerStatus.textContent = statusLine(job);
      }
      if (footerDetail) {
        footerDetail.textContent = currentPath
          ? `Current file: ${currentPath}`
          : "You can leave this page. SafeSweep keeps scanning locally.";
      }
      setFooterState("running");
      setOrbState("running");
      return;
    }

    if (status === "queued") {
      title.textContent = "Scan queued";
      subtitle.textContent = "SafeSweep is preparing the background scan.";
      path.textContent = "Waiting for the scanner...";
      bar.classList.add("is-running");
      bar.classList.remove("is-complete");
      counts.textContent = `${formatCount(filesScanned)} files scanned`;
      detail.textContent = `${formatCount(filesHashed)} hashed`;
      if (footerStatus) {
        footerStatus.textContent = "Scan queued";
      }
      if (footerDetail) {
        footerDetail.textContent = "You can leave this page. SafeSweep will reconnect when you return.";
      }
      setFooterState("running");
      setOrbState("running");
      return;
    }

    if (status === "completed") {
      title.textContent = "Scan complete";
      subtitle.textContent = `Finished scanning ${formatCount(filesScanned)} files and hashing ${formatCount(filesHashed)} of them.`;
      path.textContent = job.current_path ? `Review folder: ${compactPath(job.current_path, 3)}` : "Review folder ready.";
      bar.classList.remove("is-running");
      bar.classList.add("is-complete");
      counts.textContent = `${formatCount(filesScanned)} files scanned`;
      detail.textContent = `${formatCount(filesHashed)} hashed`;
      if (footerStatus) {
        footerStatus.textContent = "Scan complete";
      }
      if (footerDetail) {
        footerDetail.textContent = "Review the results when you are ready.";
      }
      setFooterState("completed");
      setOrbState("completed");
      return;
    }

    if (status === "failed") {
      title.textContent = "Scan paused by error";
      subtitle.textContent = "The scan stopped before it could finish.";
      path.textContent = currentLabel;
      bar.classList.remove("is-running");
      bar.classList.remove("is-complete");
      counts.textContent = `${formatCount(filesScanned)} files scanned`;
      detail.textContent = `${formatCount(filesHashed)} hashed`;
      if (footerStatus) {
        footerStatus.textContent = "Scan paused";
      }
      if (footerDetail) {
        footerDetail.textContent = "Check permissions or try a smaller folder set.";
      }
      setFooterState("failed");
      setOrbState("failed");
      return;
    }

    title.textContent = "Ready to scan";
    subtitle.textContent = "Press Start Safe Review Scan to begin.";
    path.textContent = "No file yet.";
    bar.classList.remove("is-running");
    bar.classList.remove("is-complete");
    counts.textContent = "0 files scanned";
    detail.textContent = "0 hashed";
    if (footerStatus) {
      footerStatus.textContent = "Ready to scan";
    }
    if (footerDetail) {
      footerDetail.textContent = "Choose folders, then start the scan.";
    }
    setFooterState("idle");
    setOrbState("idle");
  }

  function renderClassifications(scan) {
    const container = document.getElementById("summary-classifications");
    if (!container) {
      return;
    }
    container.innerHTML = `
      <span class="exclusion-chip">Confirmed ${scan.confirmed_duplicate_groups || 0}</span>
      <span class="exclusion-chip">Likely ${scan.likely_duplicate_groups || 0}</span>
    `;
  }

  function renderScanErrors(scan) {
    const container = document.getElementById("summary-error-list");
    if (!container) {
      return;
    }
    const errors = scan.error_samples || [];
    if (!errors.length) {
      container.classList.add("hidden");
      container.innerHTML = "";
      return;
    }
    container.classList.remove("hidden");
    container.innerHTML = `
      <div class="font-semibold">Some paths could not be scanned</div>
      <div class="mt-2 space-y-1">
        ${errors
          .slice(0, 5)
          .map((error) => `<div>${escapeHtml(error.path)} - ${escapeHtml(error.message || error.kind)}</div>`)
          .join("")}
      </div>
    `;
    if (hasPermissionError(errors)) {
      showPermissionModal(errors);
    }
  }

  function hasPermissionError(errors) {
    return errors.some((error) => {
      const kind = String(error.kind || "").toLowerCase();
      const message = String(error.message || "").toLowerCase();
      return (
        kind.includes("permission") ||
        message.includes("operation not permitted") ||
        message.includes("permission denied")
      );
    });
  }

  function setupPermissionModal() {
    const close = document.getElementById("permission-close");
    const dismiss = document.getElementById("permission-dismiss");
    const openSettings = document.getElementById("permission-open-settings");

    [close, dismiss].forEach((button) => {
      if (button) {
        button.addEventListener("click", hidePermissionModal);
      }
    });

    if (openSettings) {
      openSettings.addEventListener("click", async () => {
        openSettings.disabled = true;
        const originalText = openSettings.textContent;
        openSettings.textContent = "Opening...";
        try {
          const payload = await getJson("/api/open-privacy-settings", { method: "POST" });
          text("scan-status", payload.message || "Privacy settings opened.");
        } catch (error) {
          text("scan-status", error.message);
        } finally {
          openSettings.disabled = false;
          openSettings.textContent = originalText;
        }
      });
    }
  }

  function showPermissionModal(errors) {
    const modal = document.getElementById("permission-modal");
    const paths = document.getElementById("permission-paths");
    if (!modal) {
      return;
    }
    if (paths) {
      const permissionErrors = errors.filter((error) => hasPermissionError([error]));
      paths.innerHTML = permissionErrors
        .slice(0, 5)
        .map((error) => `<div>${escapeHtml(error.path || "Unknown path")}</div>`)
        .join("");
    }
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  }

  function hidePermissionModal() {
    const modal = document.getElementById("permission-modal");
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }

  const resultsState = {
    scan: null,
    groups: [],
    cleanupCandidates: [],
    approvals: {},
    counts: {},
    selectedGroupIds: new Set(),
    currentFlowStatus: "",
    currentFileType: "",
    previewPath: "",
  };

  async function setupResultsPage() {
    const params = new URLSearchParams(window.location.search);
    resultsState.currentFlowStatus = params.get("status") || "";
    bindResultsControls();
    bindResultsShortcuts();
    const scanId = await resolveResultsScanId();
    if (!scanId) {
      showResultsMessage("Run a scan first, then come back to Results.");
      text("results-subtitle", "No scan is available in this server session.");
      return;
    }

    await loadResults(scanId);
    updateFlowTabs();
  }

  function bindResultsControls() {
    ["results-search", "results-sort", "results-file-type"].forEach((id) => {
      const element = document.getElementById(id);
      if (element) {
        element.addEventListener("input", () => {
          syncFileTypeFilter();
          renderResults();
          renderCleanupCandidates();
        });
        element.addEventListener("change", () => {
          syncFileTypeFilter();
          resultsState.selectedGroupIds.clear();
          renderResults();
          renderCleanupCandidates();
        });
      }
    });

    // Flow tab navigation
    document.querySelectorAll(".results-flow-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        resultsState.currentFlowStatus = tab.dataset.status || "";
        updateFlowTabs();
        updateActionPanel();
        renderResults();
        resultsState.selectedGroupIds.clear();
        updateSelectionUI();
      });
    });

    const selectVisible = document.getElementById("select-visible-groups");
    if (selectVisible) {
      selectVisible.addEventListener("change", () => {
        if (selectVisible.checked) {
          filteredGroups()
            .filter((group) => isSelectableGroup(group))
            .forEach((group) => resultsState.selectedGroupIds.add(group.group_id));
        } else {
          filteredGroups().forEach((group) => resultsState.selectedGroupIds.delete(group.group_id));
        }
        renderResults();
      });
    }
    const bulkApprove = document.getElementById("bulk-approve-selected");
    if (bulkApprove) {
      bulkApprove.addEventListener("click", () => performBulkGroupAction("approve-groups"));
    }
    const bulkIgnore = document.getElementById("bulk-ignore-selected");
    if (bulkIgnore) {
      bulkIgnore.addEventListener("click", () => performBulkGroupAction("ignore-groups"));
    }
    const clearSelected = document.getElementById("clear-selected-groups");
    if (clearSelected) {
      clearSelected.addEventListener("click", () => {
        resultsState.selectedGroupIds.clear();
        renderResults();
      });
    }
    bindPreviewModal();
  }

  function bindResultsShortcuts() {
    window.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        const search = document.getElementById("results-search");
        if (search) {
          event.preventDefault();
          search.focus();
          search.select();
        }
      }
    });
  }

  async function resolveResultsScanId() {
    const params = new URLSearchParams(window.location.search);
    const scanId = params.get("scan_id");
    if (scanId) {
      return scanId;
    }
    const dashboard = await getJson("/api/dashboard");
    return dashboard.latest_scan ? dashboard.latest_scan.scan_id : "";
  }

  async function loadResults(scanId) {
    const [scanPayload, groupsPayload, cleanupPayload, approvalsPayload] = await Promise.all([
      getJson(`/api/scan/${encodeURIComponent(scanId)}`),
      getJson(`/api/scan/${encodeURIComponent(scanId)}/groups`),
      getJson(`/api/scan/${encodeURIComponent(scanId)}/cleanup-candidates`),
      getJson(`/api/scan/${encodeURIComponent(scanId)}/approvals`),
    ]);
    resultsState.scan = scanPayload.scan;
    resultsState.groups = groupsPayload.groups || [];
    resultsState.selectedGroupIds = new Set();
    resultsState.cleanupCandidates = cleanupPayload.cleanup_candidates || [];
    resultsState.approvals = (approvalsPayload.state && approvalsPayload.state.groups) || {};
    resultsState.counts = approvalsPayload.counts || {};
    text(
      "results-subtitle",
      `${resultsState.groups.length} duplicate groups and ${resultsState.cleanupCandidates.length} cleanup candidates from ${resultsState.scan.review_folder}`
    );
    renderFileTypeOptions();
    updateResultCounts();
    renderResults();
    renderCleanupCandidates();
  }

  function syncFileTypeFilter() {
    const select = document.getElementById("results-file-type");
    resultsState.currentFileType = select ? select.value : "";
  }

  function renderFileTypeOptions() {
    const select = document.getElementById("results-file-type");
    if (!select) {
      return;
    }
    const previous = select.value;
    const counts = fileTypeCounts();
    const options = Array.from(counts.entries()).sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    });
    select.innerHTML = [
      `<option value="">All file types</option>`,
      ...options.map(([type, count]) => `<option value="${escapeHtml(type)}">${escapeHtml(type)} ${count}</option>`),
    ].join("");
    const hasPrevious = options.some(([type]) => type === previous);
    select.value = hasPrevious ? previous : "";
    resultsState.currentFileType = select.value;
  }

  function fileTypeCounts() {
    const counts = new Map();
    const add = (record) => {
      const type = recordFileType(record);
      if (!type) {
        return;
      }
      counts.set(type, (counts.get(type) || 0) + 1);
    };
    resultsState.groups.forEach((group) => {
      add(group.actual);
      (group.duplicates || []).forEach(add);
    });
    resultsState.cleanupCandidates.forEach((candidate) => add(candidate.record || {}));
    return counts;
  }

  function recordFileType(record) {
    const label = extensionLabel(record).trim().toUpperCase();
    if (!label || label === "FILE") {
      return "";
    }
    return label;
  }

  function groupMatchesFileType(group, fileType) {
    if (!fileType) {
      return true;
    }
    const records = [group.actual, ...(group.duplicates || [])];
    return records.some((record) => recordFileType(record) === fileType);
  }

  function candidateMatchesFileType(candidate, fileType) {
    if (!fileType) {
      return true;
    }
    return recordFileType(candidate.record || {}) === fileType;
  }

  function updateResultCounts() {
    const confirmed = resultsState.groups.filter((group) => group.classification === "confirmed_duplicate").length;
    const likely = resultsState.groups.filter((group) => group.classification === "very_likely_duplicate").length;
    const cleanupBytes = resultsState.cleanupCandidates.reduce(
      (total, candidate) => total + Number((candidate.record && candidate.record.size_bytes) || 0),
      0
    );
    const duplicateBytes = resultsState.groups.reduce(
      (total, group) => total + Number(group.duplicate_bytes || 0),
      0
    );
    const recoveredBytes = Number(resultsState.counts.recovered_bytes || 0);
    const cleanedBytes = Number(resultsState.counts.cleaned_bytes || 0);
    const recoveredFiles = Number(resultsState.counts.recovered_files || 0);
    const cleanedFiles = Number(resultsState.counts.cleaned_files || 0);
    const fallbackRecoveredBytes = resultsState.groups.reduce((total, group) => {
      return groupApprovalStatus(group.group_id) === "moved" ? total + Number(group.duplicate_bytes || 0) : total;
    }, 0);
    const fallbackRecoveredFiles = resultsState.groups.reduce((total, group) => {
      return groupApprovalStatus(group.group_id) === "moved" ? total + Number((group.duplicates || []).length) : total;
    }, 0);
    const displayedRecoveredBytes = recoveredBytes > 0 ? recoveredBytes : fallbackRecoveredBytes;
    const displayedRecoveredFiles = recoveredFiles > 0 ? recoveredFiles : fallbackRecoveredFiles;
    const reviewed = resultsState.groups.filter((group) => groupApprovalStatus(group.group_id) !== "unreviewed").length;
    const approvedCount = resultsState.counts.approved_groups || 0;
    const movedCount = resultsState.counts.moved_groups || 0;
    const ignoredCount = resultsState.counts.ignored_groups || 0;

    text("results-groups-count", String(resultsState.groups.length));
    text("results-cleanup-count", String(resultsState.cleanupCandidates.length));
    text("results-approved-count", String(approvedCount));
    text("results-ignored-count", String(ignoredCount));
    text("results-moved-count", String(movedCount));
    text("results-reviewed-count", String(reviewed));
    text("results-recoverable-space", formatBytes(duplicateBytes + cleanupBytes));
    text("results-recovered-space", formatBytes(displayedRecoveredBytes));
    text("results-recovered-detail", `${displayedRecoveredFiles} file${displayedRecoveredFiles === 1 ? "" : "s"} awaiting sweep`);
    text("results-cleaned-space", formatBytes(cleanedBytes));
    text("results-cleaned-detail", `${cleanedFiles} file${cleanedFiles === 1 ? "" : "s"} permanently swept`);
    text("results-confirmed-breakdown", `${confirmed} confirmed · ${likely} likely`);
    text("chip-all-count", String(resultsState.groups.filter((g) => groupApprovalStatus(g.group_id) === "unreviewed").length));
    text("chip-approved-count", String(approvedCount));
    text("chip-moved-count", String(movedCount));
    text("chip-ignored-count", String(ignoredCount));
    text("results-sidebar-scan", resultsState.scan ? resultsState.scan.completed_at || resultsState.scan.scan_id : "No scan loaded");
    updateActionPanel();
  }

  function updateFlowTabs() {
    document.querySelectorAll(".results-flow-tab").forEach((tab) => {
      const status = tab.dataset.status || "";
      const isActive = status === resultsState.currentFlowStatus;
      tab.classList.toggle("results-flow-tab-active", isActive);
    });
  }

  function updateActionPanel() {
    const panel = document.getElementById("action-panel");
    const title = document.getElementById("action-title");
    const description = document.getElementById("action-description");
    const buttons = document.getElementById("action-buttons");
    const selectionSection = document.getElementById("selection-section");

    if (!panel || !title || !description || !buttons) {
      return;
    }

    const status = resultsState.currentFlowStatus;
    const approved = resultsState.counts.approved_groups || 0;
    const moved = resultsState.counts.moved_groups || 0;
    const unreviewed = resultsState.groups.filter((g) => groupApprovalStatus(g.group_id) === "unreviewed").length;

    // Show/hide selection UI only in "Need Review" tab where selection is meaningful
    if (selectionSection) {
      if (status === "") {
        selectionSection.classList.remove("hidden");
      } else {
        selectionSection.classList.add("hidden");
      }
    }

    let panelHTML = "";
    if (status === "") {
      title.textContent = "Step 1: Review & Approve";
      description.textContent = "Select which duplicates to move to the Vault. Actual files stay in place until you confirm.";
      panelHTML = `
        <div class="text-sm text-[#8a641e]">
          Use the selection bar above to approve or ignore visible groups.
        </div>
      `;
    } else if (status === "approved") {
      title.textContent = "Step 2: Move to Vault";
      description.textContent = `You have ${approved} approved group(s). Move them to the SafeSweep Vault where they're recoverable until you permanently delete.`;
      panelHTML = `
        <button id="move-approved" class="h-10 rounded-lg bg-[#955f14] px-4 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(149,95,20,0.20)] hover:bg-[#7e4f0f] disabled:cursor-not-allowed disabled:opacity-45 flex items-center gap-2" 
                onclick="performScanAction('move-approved')" 
                ${approved === 0 ? "disabled" : ""}>
          <span class="move-approved-text">Move ${approved} to Vault</span>
          <span class="move-approved-spinner hidden">
            <svg class="inline h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </span>
        </button>
      `;
    } else if (status === "moved") {
      title.textContent = "Step 3: Permanent Sweep";
      description.textContent = `You have ${moved} group(s) in the Vault. Type the confirmation phrase to permanently delete — this cannot be undone.`;
      panelHTML = `
        <button id="restore-files" class="h-10 rounded-lg border border-[#d8deea] bg-white px-4 text-sm font-semibold text-[#344054] hover:bg-[#f9fafb] disabled:cursor-not-allowed disabled:opacity-45 flex items-center gap-2" 
                onclick="performScanAction('restore')">
          <span class="restore-text">Restore from Vault</span>
          <span class="restore-spinner hidden">
            <svg class="inline h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </span>
        </button>
        <button id="purge-vault" class="h-10 rounded-lg bg-[#a7362a] px-4 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(167,54,42,0.20)] hover:bg-[#8f2f25] disabled:cursor-not-allowed disabled:opacity-45 flex items-center gap-2" 
                onclick="performScanAction('purge-vault')" 
                ${moved === 0 ? "disabled" : ""}>
          <span class="purge-text">Permanent Sweep ${moved} Group${moved === 1 ? "" : "s"}</span>
          <span class="purge-spinner hidden">
            <svg class="inline h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </span>
        </button>
      `;
    } else if (status === "ignored") {
      title.textContent = "Ignored Groups";
      description.textContent = "These duplicates won't be reviewed again. You can still restore them by going back to approved groups.";
      panelHTML = ``;
    }

    buttons.innerHTML = panelHTML;
  }

  function updateSelectionUI() {
    const checkbox = document.getElementById("select-visible-groups");
    const count = document.getElementById("selected-groups-count");
    if (checkbox) {
      checkbox.checked = false;
    }
    if (count) {
      count.textContent = "0 selected";
    }
  }

  function updateApprovedActionControls() {
    const approvedGroups = Number(resultsState.counts.approved_groups || 0);
    const movedGroups = Number(resultsState.counts.moved_groups || 0);
    const purgedGroups = Number(resultsState.counts.purged_groups || 0);
    const moveApproved = document.getElementById("move-approved");
    const purgeVault = document.getElementById("purge-vault");
    const summary = document.getElementById("approved-action-summary");
    if (moveApproved) {
      moveApproved.disabled = approvedGroups === 0;
      moveApproved.textContent = approvedGroups > 0 ? `Move ${approvedGroups} Approved to Vault` : "Move Approved to Vault";
    }
    if (purgeVault) {
      purgeVault.disabled = movedGroups === 0;
      purgeVault.textContent = movedGroups > 0 ? `Permanent Sweep ${movedGroups} Vault Group${movedGroups === 1 ? "" : "s"}` : "Permanent Sweep Vault";
    }
    if (summary) {
      if (approvedGroups > 0) {
        summary.textContent = `${approvedGroups} approved group(s) are ready to move. Actual files stay in place and restore maps will be written.`;
      } else if (movedGroups > 0) {
        summary.textContent = `${movedGroups} group(s) are in the SafeSweep Vault. You can restore them or permanently sweep the Vault copy.`;
      } else if (purgedGroups > 0) {
        summary.textContent = `${purgedGroups} group(s) were permanently swept from the Vault and can no longer be restored from SafeSweep.`;
      } else {
        summary.textContent = "Approve groups first, then move them into the recoverable SafeSweep Vault.";
      }
    }
  }

  function renderResults() {
    const container = document.getElementById("groups-list");
    if (!container) {
      return;
    }
    const visible = filteredGroups();
    if (visible.length === 0) {
      container.innerHTML =
        '<div class="rounded-lg border border-dashed border-[#cfdbe2] bg-white p-6 text-sm text-[#657382]">No groups match the current filters.</div>';
      updateSelectionControls();
      return;
    }
    container.innerHTML = visible.map(renderGroupCard).join("");
    container.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.action;
        const groupId = button.dataset.groupId;
        performScanAction(action, groupId);
      });
    });
    container.querySelectorAll("[data-select-group]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const groupId = checkbox.dataset.selectGroup;
        if (checkbox.checked) {
          resultsState.selectedGroupIds.add(groupId);
        } else {
          resultsState.selectedGroupIds.delete(groupId);
        }
        updateSelectionControls();
      });
    });
    container.querySelectorAll("[data-preview-path]").forEach((button) => {
      button.addEventListener("click", () => openFilePreview(button.dataset.previewPath || ""));
    });
    updateSelectionControls();
  }

  function filteredGroups() {
    const search = (document.getElementById("results-search")?.value || "").toLowerCase();
    const flowStatus = resultsState.currentFlowStatus;
    const fileType = resultsState.currentFileType;
    const sort = document.getElementById("results-sort")?.value || "confidence";
    let groups = resultsState.groups.filter((group) => {
      const groupStatus = groupApprovalStatus(group.group_id);
      const haystack = [
        group.group_id,
        group.classification,
        group.actual.path,
        ...(group.duplicates || []).map((record) => record.path),
      ]
        .join(" ")
        .toLowerCase();

      // Filter by flow status
      let statusMatch = true;
      if (flowStatus === "") {
        statusMatch = groupStatus === "unreviewed";
      } else if (flowStatus === "approved") {
        statusMatch = groupStatus === "approved";
      } else if (flowStatus === "moved") {
        statusMatch = groupStatus === "moved";
      } else if (flowStatus === "ignored") {
        statusMatch = groupStatus === "ignored";
      }

      return (!search || haystack.includes(search)) && statusMatch && groupMatchesFileType(group, fileType);
    });

    groups = groups.slice();
    groups.sort((left, right) => {
      if (sort === "size") {
        return Number(right.duplicate_bytes || 0) - Number(left.duplicate_bytes || 0);
      }
      if (sort === "classification") {
        return left.classification.localeCompare(right.classification);
      }
      return Number(right.confidence || 0) - Number(left.confidence || 0);
    });
    return groups;
  }

  function isSelectableGroup(group) {
    const status = groupApprovalStatus(group.group_id);
    return group.classification !== "name_collision" && status !== "moved" && status !== "restored" && status !== "purged";
  }

  function selectedGroupIds() {
    return Array.from(resultsState.selectedGroupIds).filter((groupId) => {
      const group = resultsState.groups.find((item) => item.group_id === groupId);
      return group && isSelectableGroup(group);
    });
  }

  function updateSelectionControls() {
    const selected = selectedGroupIds();
    const visibleSelectable = filteredGroups().filter((group) => isSelectableGroup(group));
    const selectedVisible = visibleSelectable.filter((group) => resultsState.selectedGroupIds.has(group.group_id));
    const selectVisible = document.getElementById("select-visible-groups");
    const selectedCount = document.getElementById("selected-groups-count");
    const bulkApprove = document.getElementById("bulk-approve-selected");
    const bulkIgnore = document.getElementById("bulk-ignore-selected");
    const clearSelected = document.getElementById("clear-selected-groups");

    resultsState.selectedGroupIds = new Set(selected);
    text("selected-groups-count", `${selected.length} selected`);
    if (selectedCount) {
      selectedCount.classList.toggle("bg-[#eef2ff]", selected.length > 0);
      selectedCount.classList.toggle("text-[#3730a3]", selected.length > 0);
    }
    if (selectVisible) {
      selectVisible.checked = visibleSelectable.length > 0 && selectedVisible.length === visibleSelectable.length;
      selectVisible.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visibleSelectable.length;
      selectVisible.disabled = visibleSelectable.length === 0;
    }
    [bulkApprove, bulkIgnore, clearSelected].forEach((button) => {
      if (button) {
        button.disabled = selected.length === 0;
      }
    });
  }

  function renderGroupCard(group) {
    const status = groupApprovalStatus(group.group_id);
    const movable = group.classification !== "name_collision" && status !== "moved" && status !== "purged";
    const selectable = isSelectableGroup(group);
    const showCheckbox = status === "unreviewed";
    const checked = resultsState.selectedGroupIds.has(group.group_id) ? "checked" : "";
    const disabled = selectable ? "" : "disabled";
    const selectionInput = showCheckbox
      ? `<input data-select-group="${escapeHtml(group.group_id)}" type="checkbox" ${checked} ${disabled} class="mt-1 h-4 w-4 rounded border-[#cfd6e3] text-[#4f46e5] focus:ring-[#4f46e5] disabled:cursor-not-allowed disabled:opacity-35">`
      : "";
    const duplicateRows = (group.duplicates || []).map((record) => renderDuplicateItem(record)).join("");
    const title = group.actual?.name || group.group_id;
    const fileCount = (group.candidates || []).length || ((group.duplicates || []).length + 1);
    const approveButton = movable && status !== "approved"
      ? `<button data-action="approve-group" data-group-id="${escapeHtml(group.group_id)}" class="h-10 rounded-lg bg-[#4f46e5] px-4 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(79,70,229,0.22)] hover:bg-[#4338ca]">Approve Group</button>`
      : status === "approved"
        ? `<span class="inline-flex h-10 items-center rounded-lg bg-[#e9f7f1] px-4 text-sm font-semibold text-[#0d6147]">Approved</span>`
      : "";
    const ignoreButton =
      status !== "moved" && status !== "purged"
        ? `<button data-action="ignore-group" data-group-id="${escapeHtml(group.group_id)}" class="h-10 rounded-lg border border-[#d8deea] bg-white px-4 text-sm font-semibold text-[#344054] hover:bg-[#f9fafb]">Ignore</button>`
        : "";

    return `
      <article class="rounded-lg border border-[#e1e6ef] bg-white p-5 shadow-[0_18px_45px_rgba(36,45,74,0.06)]">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="flex min-w-0 gap-3">
            ${selectionInput}
            <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="${badgeClass(group.classification)}">${escapeHtml(labelForClassification(group.classification))}</span>
              <span class="rounded-md bg-[#eef2ff] px-2.5 py-1 text-xs font-semibold text-[#3730a3]">${Number(group.confidence || 0)}% match</span>
              <span class="rounded-md bg-[#f2f4f7] px-2.5 py-1 text-xs font-semibold text-[#667085]">${escapeHtml(status)}</span>
            </div>
            <h2 class="mt-3 text-lg font-semibold text-[#101828]">${escapeHtml(title)}</h2>
            <p class="mt-1 text-sm text-[#667085]">${fileCount} files · ${formatBytes(group.duplicate_bytes || 0)} potential savings</p>
            </div>
          </div>
          <div class="flex shrink-0 flex-wrap items-center gap-3">
            <div class="mr-1 text-right">
              <div class="text-xs font-semibold text-[#475467]">Potential savings</div>
              <div class="mt-1 text-xl font-semibold text-[#3331b8]">${formatBytes(group.duplicate_bytes || 0)}</div>
            </div>
            ${approveButton}
            ${ignoreButton}
          </div>
        </div>
        <div class="result-file-panel mt-4 grid overflow-hidden rounded-lg lg:grid-cols-[1fr_1.05fr]">
          <section class="border-b border-[#e3e7ef] p-4 lg:border-b-0 lg:border-r">
            <div class="mb-4 text-sm font-semibold text-[#101828]">Keeping (Actual File)</div>
            ${renderActualItem(group.actual)}
          </section>
          <section class="p-4">
            <div class="mb-4 text-sm font-semibold text-[#101828]">Duplicates (Move to Vault)</div>
            <div class="space-y-3">${duplicateRows}</div>
          </section>
        </div>
        <div class="match-strip mt-4">
          ${renderMatchReasons(group)}
        </div>
      </article>
    `;
  }

  function renderActualItem(record) {
    return `
      <div class="flex gap-4">
        <div class="file-type-tile">${escapeHtml(extensionLabel(record))}</div>
        <div class="min-w-0 flex-1">
          <div class="break-words text-sm font-semibold text-[#101828]">${escapeHtml(record.name || "")}</div>
          <div class="mt-1 break-words text-sm text-[#667085]">${escapeHtml(shortPath(record.path))}</div>
          <div class="mt-1 text-xs text-[#667085]">${formatBytes(record.size_bytes)} · ${escapeHtml(record.modified_at || "")}</div>
          <div class="mt-3 flex flex-wrap gap-2">
            <span class="rounded-md bg-[#eaf8ef] px-2 py-1 text-xs font-semibold text-[#14804f]">Actual left in place</span>
            <span class="rounded-md bg-[#eef2ff] px-2 py-1 text-xs font-semibold text-[#3730a3]">Selected keeper</span>
            ${renderPreviewButton(record)}
          </div>
        </div>
      </div>
    `;
  }

  function renderDuplicateItem(record) {
    return `
      <div class="flex items-start gap-3">
        <div class="mt-1 h-4 w-4 rounded bg-[#4f46e5]"></div>
        <div class="file-type-tile h-12 w-14">${escapeHtml(extensionLabel(record))}</div>
        <div class="min-w-0 flex-1">
          <div class="break-words text-sm font-semibold text-[#101828]">${escapeHtml(record.name || "")}</div>
          <div class="mt-1 break-words text-sm text-[#667085]">${escapeHtml(shortPath(record.path))}</div>
          <div class="mt-1 text-xs text-[#667085]">${formatBytes(record.size_bytes)} · ${escapeHtml(record.modified_at || "")}</div>
          <div class="mt-3">${renderPreviewButton(record)}</div>
        </div>
      </div>
    `;
  }

  function renderPreviewButton(record) {
    const path = record && record.path ? String(record.path) : "";
    if (!path) {
      return "";
    }
    return `
      <button data-preview-path="${escapeHtml(path)}" type="button" class="inline-flex h-8 items-center rounded-lg border border-[#d8deea] bg-white px-3 text-xs font-semibold text-[#344054] hover:bg-[#f9fafb]">
        Preview
      </button>
    `;
  }

  function renderMatchReasons(group) {
    if (group.classification === "confirmed_duplicate") {
      return `
        <span class="font-semibold text-[#3331b8]">Why matched:</span>
        <span>Same SHA-256 hash</span>
        <span>Same file size</span>
        <span>Byte-for-byte confirmed</span>
      `;
    }
    return `
      <span class="font-semibold text-[#3331b8]">Why matched:</span>
      <span>Same file size</span>
      <span>Same extension</span>
      <span>Similar normalized filename</span>
    `;
  }

  function renderCleanupCandidates() {
    const container = document.getElementById("cleanup-list");
    if (!container) {
      return;
    }
    const search = (document.getElementById("results-search")?.value || "").toLowerCase();
    const fileType = resultsState.currentFileType;
    const visible = resultsState.cleanupCandidates.filter((candidate) => {
      const record = candidate.record || {};
      const haystack = [
        candidate.candidate_id,
        candidate.classification,
        record.path,
        record.name,
      ]
        .join(" ")
        .toLowerCase();
      return (!search || haystack.includes(search)) && candidateMatchesFileType(candidate, fileType);
    });
    text("cleanup-subtitle", `${visible.length} item${visible.length === 1 ? "" : "s"}`);
    if (visible.length === 0) {
      container.innerHTML =
        '<div class="rounded-lg border border-dashed border-[#cfdbe2] bg-[#fbfcfc] p-4 text-sm text-[#657382]">No cleanup candidates match the current search.</div>';
      return;
    }
    container.innerHTML = visible.map(renderCleanupCandidate).join("");
    container.querySelectorAll("[data-preview-path]").forEach((button) => {
      button.addEventListener("click", () => openFilePreview(button.dataset.previewPath || ""));
    });
  }

  function renderCleanupCandidate(candidate) {
    const record = candidate.record || {};
    return `
      <article class="rounded-lg border border-[#f0dcaa] bg-[#fffaf0] p-4">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="rounded-md bg-[#fff7ed] px-2.5 py-1 text-xs font-semibold text-[#7a4b13]">${escapeHtml(labelForClassification(candidate.classification))}</span>
              <span class="rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-[#7a4b13]">${Number(candidate.confidence || 0)}% signal</span>
            </div>
            <h3 class="mt-2 text-sm font-semibold text-[#101828]">${escapeHtml(record.name || candidate.candidate_id || "")}</h3>
            <p class="mt-1 text-sm text-[#73551d]">${escapeHtml(candidate.reason || "")}</p>
            <div class="mt-2 break-words text-sm text-[#344054]">${escapeHtml(shortPath(record.path || ""))}</div>
            <div class="mt-2 text-xs text-[#657382]">Size ${formatBytes(record.size_bytes || 0)} | Modified ${escapeHtml(record.modified_at || "")}</div>
            <div class="mt-3">${renderPreviewButton(record)}</div>
          </div>
          <div class="shrink-0 text-right">
            <div class="text-xs font-semibold text-[#7a4b13]">Potential cleanup</div>
            <div class="mt-1 text-lg font-semibold text-[#b54708]">${formatBytes(record.size_bytes || 0)}</div>
          </div>
        </div>
      </article>
    `;
  }

  function bindPreviewModal() {
    const modal = document.getElementById("file-preview-modal");
    const close = document.getElementById("file-preview-close");
    const reveal = document.getElementById("file-preview-reveal");
    if (close) {
      close.addEventListener("click", closeFilePreview);
    }
    if (modal) {
      modal.addEventListener("click", (event) => {
        if (event.target === modal) {
          closeFilePreview();
        }
      });
    }
    if (reveal) {
      reveal.addEventListener("click", revealPreviewInFinder);
    }
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && modal && !modal.classList.contains("hidden")) {
        closeFilePreview();
      }
    });
  }

  async function openFilePreview(path) {
    if (!resultsState.scan || !path) {
      return;
    }
    resultsState.previewPath = path;
    const modal = document.getElementById("file-preview-modal");
    const body = document.getElementById("file-preview-body");
    const title = document.getElementById("file-preview-title");
    const meta = document.getElementById("file-preview-meta");
    const pathLabel = document.getElementById("file-preview-path");
    if (!modal || !body || !title || !meta || !pathLabel) {
      return;
    }
    title.textContent = "Loading preview...";
    meta.textContent = "";
    pathLabel.textContent = shortPath(path);
    body.innerHTML = '<div class="rounded-lg border border-[#e1e6ef] bg-white p-5 text-sm text-[#667085]">Loading preview...</div>';
    modal.classList.remove("hidden");
    modal.classList.add("flex");

    try {
      const payload = await getJson(
        `/api/file-preview?scan_id=${encodeURIComponent(resultsState.scan.scan_id)}&path=${encodeURIComponent(path)}`
      );
      title.textContent = payload.name || "Preview";
      meta.textContent = `${payload.size_label || "0 B"} · ${payload.content_type || "unknown type"}`;
      pathLabel.textContent = shortPath(payload.path || path);
      body.innerHTML = renderPreviewBody(payload, path);
    } catch (error) {
      title.textContent = "Preview unavailable";
      meta.textContent = "";
      body.innerHTML = `
        <div class="rounded-lg border border-[#f0dcaa] bg-[#fffaf0] p-5 text-sm text-[#73551d]">
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }

  function closeFilePreview() {
    const modal = document.getElementById("file-preview-modal");
    const body = document.getElementById("file-preview-body");
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    if (body) {
      body.innerHTML = "";
    }
  }

  function renderPreviewBody(payload, requestedPath) {
    const source = `/api/file-preview/content?scan_id=${encodeURIComponent(resultsState.scan.scan_id)}&path=${encodeURIComponent(requestedPath)}`;
    if (payload.kind === "image") {
      return `<div class="flex min-h-[360px] items-center justify-center"><img class="max-h-[68vh] max-w-full rounded-lg border border-[#e1e6ef] bg-white object-contain" alt="${escapeHtml(payload.name || "Preview")}" src="${source}"></div>`;
    }
    if (payload.kind === "pdf") {
      return `<iframe class="h-[68vh] w-full rounded-lg border border-[#e1e6ef] bg-white" src="${source}" title="${escapeHtml(payload.name || "PDF preview")}"></iframe>`;
    }
    if (payload.kind === "video") {
      return `<video class="max-h-[68vh] w-full rounded-lg border border-[#e1e6ef] bg-black" src="${source}" controls></video>`;
    }
    if (payload.kind === "audio") {
      return `
        <div class="rounded-lg border border-[#e1e6ef] bg-white p-6">
          <div class="mb-4 text-sm font-semibold text-[#101828]">${escapeHtml(payload.name || "Audio preview")}</div>
          <audio class="w-full" src="${source}" controls></audio>
        </div>
      `;
    }
    if (payload.kind === "text") {
      return `<pre class="max-h-[68vh] overflow-auto rounded-lg border border-[#e1e6ef] bg-white p-5 text-sm leading-6 text-[#1d2739]">${escapeHtml(payload.snippet || "")}</pre>`;
    }
    return `
      <div class="rounded-lg border border-[#e1e6ef] bg-white p-6">
        <div class="text-base font-semibold text-[#101828]">Preview is not available for this file type.</div>
        <p class="mt-2 text-sm leading-6 text-[#667085]">SafeSweep can still show the file in Finder so you can inspect it with the right app.</p>
      </div>
    `;
  }

  async function revealPreviewInFinder() {
    if (!resultsState.scan || !resultsState.previewPath) {
      return;
    }
    const reveal = document.getElementById("file-preview-reveal");
    if (reveal) {
      reveal.disabled = true;
    }
    try {
      await getJson("/api/reveal-in-finder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scan_id: resultsState.scan.scan_id,
          path: resultsState.previewPath,
        }),
      });
    } catch (error) {
      showResultsMessage(error.message);
    } finally {
      if (reveal) {
        reveal.disabled = false;
      }
    }
  }

  function badgeClass(classification) {
    if (classification === "confirmed_duplicate") {
      return "rounded-md bg-[#e9f7f1] px-2.5 py-1 text-xs font-semibold text-[#0d6147]";
    }
    if (classification === "very_likely_duplicate") {
      return "rounded-md bg-[#fff7ed] px-2.5 py-1 text-xs font-semibold text-[#b54708]";
    }
    if (classification === "name_collision") {
      return "rounded-md bg-[#fff7ed] px-2.5 py-1 text-xs font-semibold text-[#7a4b13]";
    }
    return "rounded-md bg-[#eef3f5] px-2.5 py-1 text-xs font-semibold text-[#536170]";
  }

  function labelForClassification(classification) {
    return {
      confirmed_duplicate: "Confirmed",
      very_likely_duplicate: "Very likely",
      possible_duplicate: "Possible",
      name_collision: "Name collision",
      office_temp_lock_file: "Office temp lock",
    }[classification] || classification;
  }

  function groupApprovalStatus(groupId) {
    return (resultsState.approvals[groupId] && resultsState.approvals[groupId].status) || "unreviewed";
  }

  async function performBulkGroupAction(action) {
    if (!resultsState.scan) {
      return;
    }
    const groupIds = selectedGroupIds();
    if (groupIds.length === 0) {
      return;
    }
    if (action === "approve-groups") {
      const ok = window.confirm(`Approve ${groupIds.length} selected group(s)? Actual files stay in place.`);
      if (!ok) {
        return;
      }
    }
    setResultsActionBusy(true);
    showResultsMessage(`Processing ${action.replace(/-/g, " ")}...`);
    try {
      const payload = await getJson(
        `/api/scan/${encodeURIComponent(resultsState.scan.scan_id)}/${encodeURIComponent(action)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ group_ids: groupIds }),
        }
      );
      resultsState.approvals = (payload.state && payload.state.groups) || resultsState.approvals;
      resultsState.counts = payload.counts || resultsState.counts;
      resultsState.selectedGroupIds.clear();
      updateResultCounts();
      renderResults();
      renderCleanupCandidates();
      hideResultsMessage();
    } finally {
      setResultsActionBusy(false);
    }
  }

  async function performScanAction(action, groupId) {
    if (!resultsState.scan) {
      return;
    }
    if (action === "move-approved") {
      const ok = window.confirm(
        "Move approved duplicate candidates into the SafeSweep Vault? Actual files stay in place and a restore map will be written."
      );
      if (!ok) {
        return;
      }
    }
    if (action === "restore") {
      const ok = window.confirm(
        "Restore moved files from the SafeSweep Vault? Existing original paths will never be overwritten."
      );
      if (!ok) {
        return;
      }
    }
    let body = groupId ? { group_id: groupId } : {};
    if (action === "purge-vault") {
      const ok = window.confirm(
        "Permanent Sweep removes moved files from the SafeSweep Vault. After this, SafeSweep cannot restore those purged files. Continue?"
      );
      if (!ok) {
        return;
      }
      const phrase = window.prompt('Type "PERMANENT SWEEP" to permanently remove moved Vault files.');
      if (phrase !== "PERMANENT SWEEP") {
        showResultsMessage("Permanent sweep cancelled. Confirmation phrase did not match.");
        return;
      }
      body = { confirmation_phrase: phrase };
    }
    setResultsActionBusy(true);
    try {
      const payload = await getJson(
        `/api/scan/${encodeURIComponent(resultsState.scan.scan_id)}/${encodeURIComponent(action)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      resultsState.approvals = (payload.state && payload.state.groups) || resultsState.approvals;
      resultsState.counts = payload.counts || resultsState.counts;
      updateResultCounts();
      if (payload.move) {
        hideResultsMessage();
      } else if (payload.restore) {
        showResultsMessage(`Restored ${payload.restore.restored_count} file(s), skipped ${payload.restore.skipped_count}.`);
      } else if (payload.purge) {
        const cleanedBytes = formatBytes(payload.counts?.cleaned_bytes || 0);
        showResultsMessage(`Permanently swept ${payload.purge.purged_count} file(s), cleaned ${cleanedBytes}, skipped ${payload.purge.skipped_count}.`);
      } else {
        showResultsMessage("Review decision saved.");
      }
      renderResults();
      renderCleanupCandidates();
    } finally {
      setResultsActionBusy(false);
    }
  }

  function setResultsActionBusy(isBusy) {
    const ids = ["approve-confirmed", "move-approved", "restore-files", "purge-vault", "bulk-approve-selected", "bulk-ignore-selected"];
    ids.forEach((id) => {
      const button = document.getElementById(id);
      if (!button) {
        return;
      }
      button.disabled = isBusy;
      
      // Show/hide spinners
      const spinners = button.querySelectorAll('[class$="-spinner"]');
      spinners.forEach(spinner => {
        if (isBusy) {
          spinner.classList.remove("hidden");
        } else {
          spinner.classList.add("hidden");
        }
      });
    });
    const status = document.getElementById("results-message");
    if (status) {
      status.classList.toggle("opacity-75", isBusy);
    }
  }

  function showResultsMessage(message) {
    const element = document.getElementById("results-message");
    if (!element) {
      return;
    }
    element.textContent = message;
    element.classList.remove("hidden");
  }

  function hideResultsMessage() {
    const element = document.getElementById("results-message");
    if (!element) {
      return;
    }
    element.textContent = "";
    element.classList.add("hidden");
  }

  // Expose functions to window for onclick handlers in dynamically generated HTML
  window.performScanAction = performScanAction;
  window.performBulkGroupAction = performBulkGroupAction;

  if (page === "dashboard") {
    loadDashboard().catch(() => {
      text("latest-subtitle", "Home data could not be loaded.");
    });
  }

  if (page === "scan") {
    setupScanPage();
  }

  if (page === "results") {
    setupResultsPage().catch((error) => {
      showResultsMessage(error.message);
      text("results-subtitle", "Results could not be loaded.");
    });
  }
})();
