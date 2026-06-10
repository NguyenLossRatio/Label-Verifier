const labelImage = document.querySelector("#labelImage");
const preview = document.querySelector("#preview");
const previewFrame = document.querySelector(".preview-frame");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const rawTextOverride = document.querySelector("#rawTextOverride");
const expectedFields = document.querySelector("#expectedFields");
const verifyButton = document.querySelector("#verifyButton");
const statusOutput = document.querySelector("#status");
const results = document.querySelector("#results");

const fieldOrder = [
  "brand_name",
  "class_type",
  "alcohol_content",
  "net_contents",
  "bottler_address",
  "country_of_origin",
  "government_warning",
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

function renderFieldRow(result) {
  const label = result?.label || result?.field || "Field";
  const status = result?.status || "needs_review";

  return `
    <article class="result-row">
      <div class="field-title">
        <span>${escapeHtml(label)}</span>
        <span class="field-status ${escapeHtml(status)}">${escapeHtml(formatStatus(status))}</span>
      </div>
      <div class="field-detail">
        <p><strong>Expected:</strong> ${escapeHtml(result?.expected || "")}</p>
        <p><strong>Extracted:</strong> ${escapeHtml(result?.extracted || "") || "<em>Not found</em>"}</p>
        <p><strong>Message:</strong> ${escapeHtml(result?.message || "")}</p>
      </div>
    </article>
  `;
}

function renderResults(data) {
  const overallStatus = data?.overall_status || "needs_review";
  const processingMs = Number(data?.processing_ms ?? 0);
  const extractionMs = Number(data?.extraction_ms ?? 0);
  const fieldResults = data?.field_results || {};
  const rows = fieldOrder
    .filter((fieldName) => fieldResults[fieldName])
    .map((fieldName) => renderFieldRow(fieldResults[fieldName]))
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

labelImage.addEventListener("change", () => {
  const file = labelImage.files[0];

  if (!file) {
    preview.removeAttribute("src");
    previewFrame.classList.remove("has-image");
    previewPlaceholder.textContent = "No image selected";
    return;
  }

  preview.src = URL.createObjectURL(file);
  previewFrame.classList.add("has-image");
  previewPlaceholder.textContent = file.name;
});

expectedFields.addEventListener("submit", async (event) => {
  event.preventDefault();

  const body = new FormData(expectedFields);
  const file = labelImage.files[0];

  if (file) {
    body.append("label_image", file);
  }

  body.append("raw_text_override", rawTextOverride.value.trim());

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
      const message = getApiErrorMessage(responseBody, "Verification failed. Please check the form and try again.");
      throw new Error(message);
    }

    renderResults(responseBody);
    setStatus(formatStatus(responseBody.overall_status), responseBody.overall_status);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Verification failed.";
    renderError(message);
    setStatus("Needs attention", "error");
  } finally {
    verifyButton.disabled = false;
  }
});
