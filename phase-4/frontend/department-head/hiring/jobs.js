(function () {
  DHNav.mount({ active: "hiring", searchPlaceholder: "Search job postings..." });

  const jobsGrid = document.getElementById("jobs-grid");
  let countdownTimer = null;

  init();

  async function init() {
    await renderJobs();
    bindModals();
    bindNewJobForm();
    bindUploadForm();
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(updateCountdowns, 1000);
  }

  async function renderJobs() {
    const jobs = await DHApi.listJobs();
    const candidates = await DHApi.listCandidates();
    jobsGrid.innerHTML = jobs.map((job) => jobCardHtml(job, candidates.filter((c) => c.jobId === job.id))).join("");

    jobsGrid.querySelectorAll("[data-upload-job]").forEach((btn) =>
      btn.addEventListener("click", () => openUploadModal(btn.dataset.uploadJob, btn.dataset.uploadTitle))
    );
    jobsGrid.querySelectorAll("[data-close-job]").forEach((btn) =>
      btn.addEventListener("click", () => handleCloseJob(btn.dataset.closeJob))
    );
    updateCountdowns();
  }

  function isLocked(job) {
    return job.status === "closed" || job.closedManually || (job.deadline && Date.now() > job.deadline);
  }

  function jobCardHtml(job, candidates) {
    const locked = isLocked(job);
    const qualChips = (job.qualifications || []).map((q) => `<span class="qual-chip">${escapeHtml(q)}</span>`).join("");
    return `
      <div class="job-card ${locked ? "closed" : ""}" data-job-id="${job.id}">
        <div class="flex justify-between items-start">
          <div>
            <div class="font-headline-md text-headline-md text-on-surface">${escapeHtml(job.title)}</div>
            <div class="text-on-surface-variant text-body-sm">${escapeHtml(job.department)}</div>
          </div>
          <span class="status-pill ${locked ? "closed" : "open"}">${locked ? "Closed" : "Open"}</span>
        </div>

        <div class="flex gap-md text-body-sm">
          <div><span class="text-on-surface font-semibold">${candidates.length}</span> <span class="text-on-surface-variant">applications</span></div>
          <div><span class="text-on-surface font-semibold">${candidates.filter((c) => c.status === "shortlisted").length}</span> <span class="text-on-surface-variant">shortlisted</span></div>
        </div>

        <div>${qualChips || '<span class="text-on-surface-variant text-body-sm">No qualifications listed</span>'}</div>

        <div class="deadline-box" data-deadline="${job.deadline || ""}" data-locked="${locked}">
          <div>
            <div class="deadline-label">${locked ? "Applications Closed" : "Application Deadline"}</div>
            <div class="deadline-value" data-countdown>${locked ? "CV uploads disabled" : "Calculating..."}</div>
          </div>
          <span class="material-symbols-outlined ${locked ? "text-on-surface-variant" : "text-primary"}">${locked ? "lock" : "hourglass_top"}</span>
        </div>

        <div class="job-actions">
          <button class="primary-btn" data-upload-job="${job.id}" data-upload-title="${escapeHtml(job.title)}" ${locked ? "disabled" : ""}>
            <span class="material-symbols-outlined text-sm">upload_file</span>Upload CV
          </button>
          <a class="text-btn" href="candidates.html?job=${job.id}"><span class="material-symbols-outlined text-sm">visibility</span>View Candidates</a>
          <button class="text-btn danger" data-close-job="${job.id}" ${locked ? "disabled" : ""}>
            <span class="material-symbols-outlined text-sm">event_busy</span>End Application Window Now
          </button>
        </div>
      </div>`;
  }

  function updateCountdowns() {
    document.querySelectorAll(".deadline-box").forEach((box) => {
      const locked = box.dataset.locked === "true";
      const deadline = Number(box.dataset.deadline);
      const el = box.querySelector("[data-countdown]");
      if (!el || locked || !deadline) return;
      const diff = deadline - Date.now();
      if (diff <= 0) {
        el.textContent = "Deadline passed — awaiting closure";
        el.classList.add("urgent");
        box.classList.add("urgent");
        return;
      }
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      el.textContent = days > 0 ? `${days}d ${hours}h remaining` : `${hours}h ${mins}m ${secs}s remaining`;
      if (diff < 3600000) {
        el.classList.add("urgent");
        box.classList.add("urgent");
      }
    });
  }

  async function handleCloseJob(jobId) {
    if (!confirm("End the application window now? No further CVs will be accepted for this posting, and this cannot be undone here.")) return;
    try {
      await DHApi.closeJob(jobId);
      showToast("Application window closed. Ready to generate a shortlist.", "success");
      await renderJobs();
    } catch (err) {
      console.error(err);
      showToast("Could not close the job posting.", "error");
    }
  }

  /* ---------------- Modals ---------------- */
  function bindModals() {
    document.getElementById("new-job-btn").addEventListener("click", () => showModal("new-job-modal"));
    document.querySelectorAll("[data-close-modal]").forEach((btn) =>
      btn.addEventListener("click", () => hideModal(btn.dataset.closeModal))
    );
    document.querySelectorAll(".modal-backdrop").forEach((backdrop) =>
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) hideModal(backdrop.id);
      })
    );
  }
  function showModal(id) { document.getElementById(id).classList.remove("hidden"); }
  function hideModal(id) { document.getElementById(id).classList.add("hidden"); }

  function bindNewJobForm() {
    const form = document.getElementById("new-job-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const title = fd.get("title").trim();
      const department = fd.get("department").trim();
      const qualifications = fd.get("qualifications").split(",").map((s) => s.trim()).filter(Boolean);
      const deadlineRaw = fd.get("deadline");
      const deadline = deadlineRaw ? new Date(deadlineRaw).getTime() : null;

      try {
        // Real endpoint: POST /hiring/jobs
        await DHApi.createJob({ title, department, qualifications, deadline });
        hideModal("new-job-modal");
        form.reset();
        showToast("Job posting created.", "success");
        await renderJobs();
      } catch (err) {
        console.error(err);
        showToast("Could not create the job posting.", "error");
      }
    });
  }

  /* ---------------- CV Upload ---------------- */
  let currentUploadJobId = null;
  let selectedFile = null;

  function openUploadModal(jobId, title) {
    currentUploadJobId = jobId;
    selectedFile = null;
    document.getElementById("upload-job-id").value = jobId;
    document.getElementById("upload-job-title").textContent = title;
    document.getElementById("upload-cv-form").reset();
    document.getElementById("dropzone-text").textContent = "Click to choose a file from your device, or drag it here (PDF, DOC, DOCX)";
    document.getElementById("dropzone").classList.remove("has-file");
    document.getElementById("upload-error").classList.add("hidden");
    showModal("upload-cv-modal");
  }

  function bindUploadForm() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("cv-file-input");

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        selectedFile = fileInput.files[0];
        document.getElementById("dropzone-text").textContent = `Selected: ${selectedFile.name}`;
        dropzone.classList.add("has-file");
      }
    });

    ["dragover", "dragenter"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
    );
    dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) {
        fileInput.files = e.dataTransfer.files;
        selectedFile = file;
        document.getElementById("dropzone-text").textContent = `Selected: ${file.name}`;
        dropzone.classList.add("has-file");
      }
    });

    document.getElementById("upload-cv-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errorBox = document.getElementById("upload-error");
      errorBox.classList.add("hidden");

      if (!selectedFile) {
        errorBox.textContent = "Please choose a CV file first.";
        errorBox.classList.remove("hidden");
        return;
      }

      const submitBtn = document.getElementById("upload-submit-btn");
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="material-symbols-outlined text-sm animate-spin">progress_activity</span>Uploading...`;

      const fd = new FormData(e.target);
      const candidateName = fd.get("candidateName");

      try {
        // Real endpoint: POST /hiring/jobs/{job_id}/cv
        await DHApi.uploadCV(currentUploadJobId, selectedFile, candidateName);
        hideModal("upload-cv-modal");
        showToast("CV submitted. It has entered parsing and AI scoring.", "success");
        await renderJobs();
      } catch (err) {
        if (err.code === "APPLICATIONS_CLOSED") {
          errorBox.textContent = "Applications are closed for this position — the deadline has passed or the Department Head ended the window. This CV was not accepted.";
        } else {
          errorBox.textContent = "Something went wrong submitting this CV. Please try again.";
        }
        errorBox.classList.remove("hidden");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span class="material-symbols-outlined text-sm">send</span>Submit CV`;
      }
    });
  }

  /* ---------------- Utilities ---------------- */
  function showToast(message, type) {
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.innerHTML = `<span class="material-symbols-outlined text-sm">${type === "error" ? "error" : "check_circle"}</span>${message}`;
    document.getElementById("toast-root").appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();
