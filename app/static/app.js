const applicationFile = document.querySelector("#applicationFile");
const preview = document.querySelector("#preview");
const previewFrame = document.querySelector(".preview-frame");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const applicationForm = document.querySelector("#applicationForm");
const applicationFields = document.querySelector("#applicationFields");
const verifyButton = document.querySelector("#verifyButton");
const statusOutput = document.querySelector("#status");
const results = document.querySelector("#results");
let currentApplicationValid = false;

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

function renderResults(data) {
  const overallStatus = data?.overall_status || "needs_review";
  const processingMs = Number(data?.processing_ms ?? 0);
  const extractionMs = Number(data?.extraction_ms ?? 0);
  const fieldResults = data?.field_results || {};
  const fieldGuesses = data?.field_guesses || {};
  const rows = fieldOrder
    .filter((fieldName) => fieldResults[fieldName])
    .map((fieldName) => renderFieldRow(fieldResults[fieldName], fieldGuesses[fieldName]))
    .join("");

  results.innerHTML = `
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

  return { ...attachment, content_type: contentType };
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

applicationFile.addEventListener("change", async () => {
  const file = applicationFile.files[0];

  resetApplicationPreview();

  if (!file) {
    setStatus("Ready");
    return;
  }

  try {
    const application = JSON.parse(await file.text());
    const attachment = validateApplication(application);

    renderApplicationFields(application);
    preview.src = `data:${attachment.content_type};base64,${attachment.data}`;
    previewFrame.classList.add("has-image");
    previewPlaceholder.textContent = attachment.filename;
    currentApplicationValid = true;
    verifyButton.disabled = !currentApplicationValid;
    results.innerHTML = '<p class="empty-state">No results yet.</p>';
    setStatus("Application loaded", "pass");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Application file could not be loaded.";
    renderError(message);
    setStatus("Needs attention", "error");
    resetApplicationPreview();
  }
});

applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = applicationFile.files[0];

  if (!file) {
    renderError("Upload a liquor application JSON file.");
    setStatus("Needs attention", "error");
    return;
  }

  const body = new FormData();
  body.append("application_file", file);

  verifyButton.disabled = true;
  setStatus("Verifying...", "busy");
  results.innerHTML = '<p class="empty-state">Review in progress...</p>';

  try {
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

    renderResults(responseBody);
    setStatus(formatStatus(responseBody.overall_status), responseBody.overall_status);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Verification failed.";
    renderError(message);
    setStatus("Needs attention", "error");
  } finally {
    verifyButton.disabled = !currentApplicationValid;
  }
});
