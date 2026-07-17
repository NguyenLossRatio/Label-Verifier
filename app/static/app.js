const applicationFile = document.querySelector("#applicationFile");
const preview = document.querySelector("#preview");
const previewFrame = document.querySelector(".preview-frame");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const applicationForm = document.querySelector("#applicationForm");
const applicationFields = document.querySelector("#applicationFields");
const applicationQueue = document.querySelector("#applicationQueue");
const verifyButton = document.querySelector("#verifyButton");
const statusOutput = document.querySelector("#status");
const results = document.querySelector("#results");
let currentApplicationValid = false;
let applicationVersion = 0;
let selectedApplications = [];
let activeApplicationIndex = -1;
let batchRunning = false;

const fieldOrder = [
  "brand_name",
  "class_type",
  "alcohol_content",
  "net_contents",
  "bottler_address",
  "country_of_origin",
  "government_warning",
];

const applicationFieldOrder = [
  ["brand_name", "Brand name"],
  ["class_type", "Class/type"],
  ["alcohol_content", "Alcohol content"],
  ["net_contents", "Net contents"],
  ["bottler_address", "Bottler/producer address"],
  ["country_of_origin", "Country of origin"],
];

const requiredApplicationFields = [
  "brand_name",
  "class_type",
  "alcohol_content",
  "net_contents",
  "bottler_address",
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatStatus(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? singular : plural;
}

function setStatus(message, state = "") {
  statusOutput.textContent = message;
  statusOutput.className = state ? `status ${state}` : "status";
}

function renderError(message) {
  results.innerHTML = `<div class="error-box" role="alert">${escapeHtml(message)}</div>`;
}

function renderFieldRow(result, detectedValue = "") {
  const label = result?.label || result?.field || "Field";
  const status = result?.status || "needs_review";
  const extracted = result?.extracted || detectedValue;
  const expected = result?.expected || "";
  const message = result?.message || "";
  const extractedMarkup = extracted
    ? `<div class="field-value">${escapeHtml(extracted)}</div>`
    : '<div class="field-value empty-value"><em>Not found</em></div>';

  return `
    <article class="result-row">
      <div class="field-title">
        <span>${escapeHtml(label)}</span>
        <span class="field-status ${escapeHtml(status)}">${escapeHtml(formatStatus(status))}</span>
      </div>
      <div class="field-detail">
        <div>
          <strong>Expected:</strong>
          <div class="field-value">${escapeHtml(expected)}</div>
        </div>
        <div>
          <strong>Extracted:</strong>
          ${extractedMarkup}
        </div>
        <div>
          <strong>Message:</strong>
          <div class="field-value">${escapeHtml(message)}</div>
        </div>
      </div>
    </article>
  `;
}

function renderResultMarkup(data) {
  const overallStatus = data?.overall_status || "needs_review";
  const processingMs = Number(data?.processing_ms ?? 0);
  const extractionMs = Number(data?.extraction_ms ?? 0);
  const fieldResults = data?.field_results || {};
  const fieldGuesses = data?.field_guesses || {};
  const rows = fieldOrder
    .filter((fieldName) => fieldResults[fieldName])
    .map((fieldName) => renderFieldRow(fieldResults[fieldName], fieldGuesses[fieldName]))
    .join("");

  return `
    <div class="summary">
      <span class="badge ${escapeHtml(overallStatus)}">${escapeHtml(formatStatus(overallStatus))}</span>
      <span class="meta">Extraction: ${escapeHtml(extractionMs)} ms</span>
      <span class="meta">Verification: ${escapeHtml(processingMs)} ms</span>
    </div>
    <div class="result-list">
      ${rows || '<p class="empty-state">No field results were returned.</p>'}
    </div>
    <details>
      <summary>Raw extracted text</summary>
      <pre class="raw-text">${escapeHtml(data?.raw_text || "")}</pre>
    </details>
  `;
}

function renderResults(data) {
  results.innerHTML = renderResultMarkup(data);
}

function getApiErrorMessage(errorBody, fallback) {
  if (!errorBody) {
    return fallback;
  }

  if (typeof errorBody.detail === "string") {
    return errorBody.detail;
  }

  if (Array.isArray(errorBody.detail)) {
    return errorBody.detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join("; ");
  }

  return fallback;
}

function resetApplicationPreview(filename = "No application selected") {
  currentApplicationValid = false;
  preview.onload = null;
  preview.onerror = null;
  preview.removeAttribute("src");
  previewFrame.classList.remove("has-image");
  previewPlaceholder.textContent = filename;
  applicationFields.hidden = true;
  applicationFields.innerHTML = "";
  verifyButton.disabled = true;
}

function requireNonblankString(value, label) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} is required in the application file.`);
  }
}

function validateApplication(application) {
  if (!application || typeof application !== "object" || Array.isArray(application)) {
    throw new Error("Application file must contain a JSON object.");
  }

  requiredApplicationFields.forEach((fieldName) => {
    requireNonblankString(application[fieldName], fieldName);
  });

  if (
    "country_of_origin" in application &&
    application.country_of_origin !== null &&
    typeof application.country_of_origin !== "string"
  ) {
    throw new Error("Application is missing required field: country_of_origin.");
  }

  const attachment = application.label_attachment;

  if (!attachment || typeof attachment !== "object" || Array.isArray(attachment)) {
    throw new Error("Application file must include a label_attachment object.");
  }

  requireNonblankString(attachment.filename, "label_attachment.filename");
  requireNonblankString(attachment.content_type, "label_attachment.content_type");
  requireNonblankString(attachment.data, "label_attachment.data");

  const contentType = attachment.content_type.toLowerCase();

  if (!contentType.startsWith("image/") || contentType === "image/") {
    throw new Error("label_attachment.content_type must be an image type.");
  }

  try {
    atob(attachment.data);
  } catch (_error) {
    throw new Error("Label attachment data must be base64-encoded image bytes.");
  }

  return { ...attachment, content_type: contentType };
}

function loadAttachmentPreview(attachment) {
  return new Promise((resolve, reject) => {
    preview.onload = () => {
      preview.onload = null;
      preview.onerror = null;
      resolve();
    };
    preview.onerror = () => {
      preview.onload = null;
      preview.onerror = null;
      reject(new Error("Label attachment data must be base64-encoded image bytes."));
    };
    preview.src = `data:${attachment.content_type};base64,${attachment.data}`;
  });
}

function renderApplicationFields(application) {
  applicationFields.innerHTML = applicationFieldOrder
    .map(([fieldName, label]) => {
      const value = application[fieldName];
      const isEmpty = typeof value !== "string" || !value.trim();
      const valueMarkup = isEmpty
        ? '<span class="field-value empty-value">Not provided</span>'
        : `<span class="field-value">${escapeHtml(value)}</span>`;

      return `
        <div class="readonly-field">
          <span>${escapeHtml(label)}</span>
          ${valueMarkup}
        </div>
      `;
    })
    .join("");
  applicationFields.hidden = false;
}

function createApplicationItem(file, index) {
  return {
    id: `${Date.now()}-${index}`,
    file,
    filename: file.name,
    application: null,
    attachment: null,
    valid: false,
    error: "",
    result: null,
    status: "loading",
  };
}

function getQueueStatus(item) {
  if (item.status === "verifying") {
    return "Verifying";
  }

  if (item.result?.overall_status) {
    return formatStatus(item.result.overall_status);
  }

  if (!item.valid || item.error) {
    return item.status === "loading" ? "Loading" : "Invalid";
  }

  return "Queued";
}

function getQueueStatusClass(item) {
  if (item.status === "verifying") {
    return "needs_review";
  }

  if (item.result?.overall_status) {
    return item.result.overall_status;
  }

  if (!item.valid || item.error) {
    return item.status === "loading" ? "needs_review" : "error";
  }

  return "queued";
}

function renderApplicationQueue() {
  if (!selectedApplications.length) {
    applicationQueue.innerHTML = '<p class="empty-state">No applications selected.</p>';
    return;
  }

  applicationQueue.innerHTML = `
    <div class="queue-heading">
      <strong>${escapeHtml(selectedApplications.length)} ${escapeHtml(pluralize(selectedApplications.length, "application"))}</strong>
      <span class="meta">${escapeHtml(selectedApplications.filter((item) => item.valid).length)} ready</span>
    </div>
    <div class="queue-list">
      ${selectedApplications
        .map((item, index) => {
          const isActive = index === activeApplicationIndex;
          const statusClass = getQueueStatusClass(item);
          const status = getQueueStatus(item);

          return `
            <button
              class="queue-item ${isActive ? "active" : ""}"
              type="button"
              data-application-index="${escapeHtml(index)}"
              aria-current="${isActive ? "true" : "false"}"
            >
              <span class="queue-name">${escapeHtml(item.filename)}</span>
              <span class="field-status ${escapeHtml(statusClass)}">${escapeHtml(status)}</span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function setVerifyAvailability() {
  currentApplicationValid = selectedApplications.some((item) => item.valid);
  verifyButton.disabled = !currentApplicationValid || batchRunning;
}

async function showActiveApplication(selectedApplicationVersion = applicationVersion) {
  const item = selectedApplications[activeApplicationIndex];
  resetApplicationPreview(item?.filename || "No application selected");

  if (!item) {
    setVerifyAvailability();
    return;
  }

  if (!item.valid) {
    renderError(item.error || "Application file could not be loaded.");
    renderApplicationQueue();
    setVerifyAvailability();
    return;
  }

  try {
    renderApplicationFields(item.application);
    await loadAttachmentPreview(item.attachment);

    if (selectedApplicationVersion !== applicationVersion) {
      return;
    }

    previewFrame.classList.add("has-image");
    previewPlaceholder.textContent = item.attachment.filename;
    renderApplicationQueue();
    renderBatchResults();
    setVerifyAvailability();
  } catch (error) {
    if (selectedApplicationVersion !== applicationVersion) {
      return;
    }

    item.valid = false;
    item.status = "error";
    item.error = error instanceof Error ? error.message : "Application file could not be loaded.";
    renderError(item.error);
    renderApplicationQueue();
    setVerifyAvailability();
  }
}

function renderSelectedApplicationResult() {
  const item = selectedApplications[activeApplicationIndex];

  if (!item) {
    return '<p class="empty-state">Select an application to review its results.</p>';
  }

  const statusClass = getQueueStatusClass(item);
  const status = getQueueStatus(item);
  const body = item.result
    ? renderResultMarkup(item.result)
    : item.error
      ? `<div class="error-box" role="alert">${escapeHtml(item.error)}</div>`
      : '<p class="empty-state">Waiting for verification.</p>';

  return `
    <article class="selected-result-card">
      <div class="batch-result-heading">
        <h3>${escapeHtml(item.filename)}</h3>
        <span class="field-status ${escapeHtml(statusClass)}">${escapeHtml(status)}</span>
      </div>
      ${body}
    </article>
  `;
}

function renderBatchResults() {
  if (!selectedApplications.length) {
    results.innerHTML = '<p class="empty-state">No results yet.</p>';
    return;
  }

  const completed = selectedApplications.filter((item) => item.result || item.error);
  const passed = selectedApplications.filter((item) => item.result?.overall_status === "pass").length;
  const review = selectedApplications.filter(
    (item) => item.result && item.result.overall_status !== "pass",
  ).length;
  const errors = selectedApplications.filter((item) => item.error).length;
  const summaryText = completed.length
    ? `${completed.length} of ${selectedApplications.length} processed`
    : "Ready to verify";

  results.innerHTML = `
    <div class="summary batch-summary">
      <span class="badge ${errors ? "error" : review ? "needs_review" : passed ? "pass" : "needs_review"}">
        ${escapeHtml(summaryText)}
      </span>
      <span class="meta">${escapeHtml(passed)} passed</span>
      <span class="meta">${escapeHtml(review)} need review</span>
      <span class="meta">${escapeHtml(errors)} failed</span>
    </div>
    <div class="batch-results">
      ${renderSelectedApplicationResult()}
    </div>
  `;
}

async function verifyApplication(item) {
  const file = item.file;
  const body = new FormData();
  body.append("application_file", file);
  const response = await fetch("/api/verify", { method: "POST", body });
  let responseBody = null;

  try {
    responseBody = await response.json();
  } catch (_error) {
    responseBody = null;
  }

  if (!response.ok) {
    const message = getApiErrorMessage(responseBody, "Verification failed. Please check the application and try again.");
    throw new Error(message);
  }

  return responseBody;
}

async function loadSelectedApplications(files, selectedApplicationVersion) {
  selectedApplications = Array.from(files).map(createApplicationItem);
  activeApplicationIndex = selectedApplications.length ? 0 : -1;
  renderApplicationQueue();
  resetApplicationPreview();

  if (!selectedApplications.length) {
    results.innerHTML = '<p class="empty-state">No results yet.</p>';
    setStatus("Ready");
    setVerifyAvailability();
    return;
  }

  for (const item of selectedApplications) {
    try {
      const applicationText = await item.file.text();

      if (selectedApplicationVersion !== applicationVersion) {
        return;
      }

      const application = JSON.parse(applicationText);
      const attachment = validateApplication(application);
      item.application = application;
      item.attachment = attachment;
      item.valid = true;
      item.status = "queued";
    } catch (error) {
      if (selectedApplicationVersion !== applicationVersion) {
        return;
      }

      item.valid = false;
      item.status = "error";
      item.error = error instanceof Error ? error.message : "Application file could not be loaded.";
    }
  }

  if (selectedApplicationVersion !== applicationVersion) {
    return;
  }

  const firstValidIndex = selectedApplications.findIndex((item) => item.valid);
  activeApplicationIndex = firstValidIndex >= 0 ? firstValidIndex : 0;
  renderApplicationQueue();
  renderBatchResults();
  await showActiveApplication(selectedApplicationVersion);

  if (selectedApplicationVersion !== applicationVersion) {
    return;
  }

  const validCount = selectedApplications.filter((item) => item.valid).length;
  const invalidCount = selectedApplications.length - validCount;

  if (validCount) {
    const invalidNote = invalidCount ? `, ${invalidCount} invalid` : "";
    setStatus(`${validCount} ${pluralize(validCount, "application")} loaded${invalidNote}`, "pass");
  } else {
    setStatus("Needs attention", "error");
  }

  setVerifyAvailability();
}

applicationQueue.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-application-index]");

  if (!button || batchRunning) {
    return;
  }

  const nextIndex = Number(button.dataset.applicationIndex);

  if (!Number.isInteger(nextIndex) || nextIndex < 0 || nextIndex >= selectedApplications.length) {
    return;
  }

  activeApplicationIndex = nextIndex;
  await showActiveApplication(applicationVersion);
});

applicationFile.addEventListener("change", async () => {
  applicationVersion += 1;
  const selectedApplicationVersion = applicationVersion;

  batchRunning = false;
  await loadSelectedApplications(applicationFile.files, selectedApplicationVersion);
});

applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const validApplications = selectedApplications.filter((item) => item.valid);

  if (!validApplications.length) {
    renderError("Upload at least one valid liquor application JSON file.");
    setStatus("Needs attention", "error");
    return;
  }

  const submittedApplicationVersion = applicationVersion;
  batchRunning = true;
  verifyButton.disabled = true;
  applicationFile.disabled = true;
  validApplications.forEach((item) => {
    item.result = null;
    item.error = "";
    item.status = "queued";
  });
  setStatus("Verifying...", "busy");
  results.innerHTML = '<p class="empty-state">Review in progress...</p>';
  renderApplicationQueue();
  renderBatchResults();

  try {
    for (const item of validApplications) {
      if (submittedApplicationVersion !== applicationVersion) {
        return;
      }

      item.status = "verifying";
      activeApplicationIndex = selectedApplications.indexOf(item);
      renderApplicationQueue();
      renderBatchResults();

      try {
        const responseBody = await verifyApplication(item);

        if (submittedApplicationVersion !== applicationVersion) {
          return;
        }

        item.result = responseBody;
        item.status = responseBody?.overall_status || "needs_review";
      } catch (error) {
        if (submittedApplicationVersion !== applicationVersion) {
          return;
        }

        item.status = "error";
        item.error = error instanceof Error ? error.message : "Verification failed.";
      }

      renderApplicationQueue();
      renderBatchResults();
    }

    if (submittedApplicationVersion !== applicationVersion) {
      return;
    }

    const hasErrors = selectedApplications.some((item) => item.error);
    const needsReview = selectedApplications.some((item) => item.result && item.result.overall_status !== "pass");
    const finalState = hasErrors ? "error" : needsReview ? "needs_review" : "pass";
    setStatus("Batch complete", finalState);
  } finally {
    if (submittedApplicationVersion === applicationVersion) {
      batchRunning = false;
      applicationFile.disabled = false;
      setVerifyAvailability();
      renderApplicationQueue();
    }
  }
});
