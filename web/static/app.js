const state = {
  commands: [],
  busy: false,
};

const healthDot = document.querySelector("#health-dot");
const healthText = document.querySelector("#health-text");
const resultMessage = document.querySelector("#result-message");
const resultText = document.querySelector("#result-text");
const resultJson = document.querySelector("#result-json");
const commandSelect = document.querySelector("#command-select");

function setHealth(ok, text) {
  healthDot.className = `dot ${ok ? "ok" : "error"}`;
  healthText.textContent = text;
}

function setBusy(isBusy) {
  state.busy = isBusy;
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = isBusy;
  });
}

function showResult(result) {
  const ok = Boolean(result && result.ok);
  resultMessage.textContent = result?.message || (ok ? "OK" : "Error");
  resultMessage.classList.toggle("error", !ok);
  resultJson.textContent = JSON.stringify(result, null, 2);

  const data = result?.data || {};
  const formatted = data.formatted || data.report_text || "";
  resultText.textContent = formatted;
  resultText.classList.toggle("visible", Boolean(formatted));

  if (data.total !== undefined) {
    updateMetrics(data);
  }
  if (Array.isArray(data.opportunities)) {
    renderOpportunityList(data.opportunities);
  }
}

function updateMetrics(data) {
  document.querySelector("#metric-total").textContent = data.total ?? "-";
  document.querySelector("#metric-active").textContent = data.active_count ?? "-";
  document.querySelector("#metric-killed").textContent = data.killed_count ?? "-";
}

function renderOpportunityList(items) {
  const target = document.querySelector("#opportunity-list");
  if (!items.length) {
    target.innerHTML = "<p class=\"message\">No opportunities</p>";
    return;
  }
  const rows = items.map((item) => `
    <tr>
      <td>${escapeHtml(item.id || "")}</td>
      <td>${escapeHtml(item.name || "")}</td>
      <td>${escapeHtml(item.stage || "")}</td>
      <td>${escapeHtml(item.status || "")}</td>
    </tr>
  `).join("");
  target.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Name</th><th>Stage</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

async function apiGet(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function runCommand(command, params = {}) {
  setBusy(true);
  try {
    const response = await fetch(`/api/commands/${encodeURIComponent(command)}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({params}),
    });
    const result = await response.json();
    showResult(result);
    return result;
  } catch (error) {
    const result = {ok: false, data: {}, message: error.message || String(error)};
    showResult(result);
    return result;
  } finally {
    setBusy(false);
  }
}

function collectParams(form) {
  const params = {};
  const fields = Array.from(form.elements).filter((field) => field.name);
  for (const field of fields) {
    if (field.type === "checkbox") {
      params[field.name] = field.checked;
      continue;
    }
    const value = field.value.trim();
    if (value === "") {
      continue;
    }
    if (field.dataset.csv !== undefined) {
      params[field.name] = value.split(",").map((item) => item.trim()).filter(Boolean);
    } else if (field.dataset.int !== undefined) {
      params[field.name] = Number.parseInt(value, 10);
    } else if (field.dataset.float !== undefined) {
      params[field.name] = Number.parseFloat(value);
    } else if (field.dataset.json !== undefined) {
      params[field.name] = JSON.parse(value);
    } else {
      params[field.name] = value;
    }
  }
  return params;
}

function wirePanels() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.panel}`).classList.add("active");
    });
  });
}

function wireForms() {
  document.querySelectorAll("form[data-command]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await runCommand(form.dataset.command, collectParams(form));
      } catch (error) {
        showResult({ok: false, data: {}, message: error.message || String(error)});
      }
    });
  });

  document.querySelectorAll("button[data-command]").forEach((button) => {
    button.addEventListener("click", () => {
      runCommand(button.dataset.command, {});
    });
  });

  document.querySelector("#advanced-runner").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const command = commandSelect.value;
      const params = JSON.parse(document.querySelector("#params-json").value || "{}");
      await runCommand(command, params);
    } catch (error) {
      showResult({ok: false, data: {}, message: error.message || String(error)});
    }
  });

  document.querySelector("#clear-result").addEventListener("click", () => {
    resultMessage.textContent = "";
    resultMessage.classList.remove("error");
    resultText.textContent = "";
    resultText.classList.remove("visible");
    resultJson.textContent = "{}";
  });
}

async function boot() {
  wirePanels();
  wireForms();
  try {
    await apiGet("/api/health");
    setHealth(true, "Connected");
    const catalog = await apiGet("/api/commands");
    state.commands = catalog.data.commands || [];
    commandSelect.innerHTML = state.commands
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`)
      .join("");
    await runCommand("status", {});
  } catch (error) {
    setHealth(false, error.message || String(error));
  }
}

boot();

