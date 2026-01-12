async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data?.detail?.error || `Request failed (${res.status})`);
    err.detail = data?.detail || data;
    throw err;
  }
  return data;
}

function ensureToastWrap() {
  let wrap = document.querySelector(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
  }
  return wrap;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function toast(kind, title, msg) {
  const wrap = ensureToastWrap();
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="t-title">${escapeHtml(title)}</div><div class="t-msg">${escapeHtml(msg)}</div>`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), kind === "err" ? 7000 : 3500);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function normalizeHost(value) {
  let v = String(value || "").trim();
  if (!v) return "";
  if (v.includes("://")) {
    try {
      v = new URL(v).host || "";
    } catch {
      // ignore
    }
  }
  if (v.includes("/")) v = v.split("/", 1)[0];
  return v.toLowerCase();
}

const PROVIDER_PRESETS = {
  github: {
    host: "github.com",
    tokenHint: "GitHub PAT with repo read access.",
    hostHint: "Example: github.com (or your GitHub Enterprise domain).",
  },
  gitlab: {
    host: "gitlab.com",
    tokenHint: "GitLab PAT with read_api.",
    hostHint: "Example: gitlab.com (or your self-hosted GitLab domain).",
  },
  bitbucket: {
    host: "bitbucket.org",
    tokenHint: "Bitbucket Cloud: store as username:app_password.",
    hostHint: "Bitbucket Cloud host is bitbucket.org.",
  },
  azure: {
    host: "dev.azure.com",
    tokenHint: "Azure DevOps PAT with Code (Read).",
    hostHint: "Use dev.azure.com (do not include https://).",
  },
  gitea: {
    host: "gitea.yourcompany.com",
    tokenHint: "Gitea token with repo read access.",
    hostHint: "Your Gitea domain (example: gitea.yourcompany.com).",
  },
};

async function refresh() {
  const res = await fetch("api/settings");
  const data = await res.json();
  renderTokens(data.tokens || {});
  document.getElementById("llm-view").textContent = pretty(data.llm || {});

  // best-effort: populate Azure OpenAI fields if present (masked values are fine for endpoint/version/deployment)
  try {
    const llm = data.llm || {};
    const p = document.getElementById("llm-provider");
    if (p && llm.provider) p.value = llm.provider;
    const ep = document.getElementById("openai-endpoint");
    if (ep && llm.openai_endpoint) ep.value = llm.openai_endpoint;
    const av = document.getElementById("openai-api-version");
    if (av && llm.openai_api_version) av.value = llm.openai_api_version;
    const dep = document.getElementById("openai-deployment");
    if (dep && llm.openai_deployment) dep.value = llm.openai_deployment;
  } catch {
    // ignore
  }
}

function renderTokens(tokens) {
  const root = document.getElementById("tokens-list");
  const providers = Object.keys(tokens || {});
  if (!providers.length) {
    root.textContent = "No tokens saved.";
    return;
  }
  const rows = [];
  for (const provider of providers) {
    const hosts = tokens[provider] || {};
    for (const host of Object.keys(hosts)) {
      rows.push({ provider, host, masked: hosts[host] });
    }
  }
  rows.sort((a, b) => (a.provider + a.host).localeCompare(b.provider + b.host));

  root.innerHTML = rows
    .map(
      (r) => `
      <div class="row" style="align-items:center; justify-content:space-between">
        <div style="min-width:0">
          <span class="pill">${escapeHtml(r.provider)}</span>
          <code>${escapeHtml(r.host)}</code>
          <span class="muted" style="margin-left:8px">${escapeHtml(r.masked)}</span>
        </div>
        <button class="button secondary" data-del="1" data-provider="${escapeHtml(r.provider)}" data-host="${escapeHtml(
        r.host
      )}">Remove</button>
      </div>
    `
    )
    .join("");

  root.querySelectorAll("button[data-del='1']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-provider");
      const host = btn.getAttribute("data-host");
      try {
        await postJson("api/settings/token/delete", { provider, host });
        toast("ok", "Token removed", `Provider: ${provider}\nHost: ${host}`);
        await refresh();
      } catch (err) {
        toast("err", "Failed to remove token", err.message || "Unknown error");
      }
    });
  });
}

window.addEventListener("DOMContentLoaded", () => {
  const tokenForm = document.getElementById("token-form");
  const llmForm = document.getElementById("llm-form");
  const llmClear = document.getElementById("llm-clear");
  const providerEl = document.getElementById("provider");
  const hostEl = document.getElementById("host");
  const tokenEl = document.getElementById("token");
  const hostHintEl = document.getElementById("host-hint");
  const tokenHintEl = document.getElementById("token-hint");

  let lastAutoHost = null;

  function applyProviderPreset() {
    const provider = providerEl.value;
    const preset = PROVIDER_PRESETS[provider] || {};
    hostEl.placeholder = preset.host || "example.com";
    tokenEl.placeholder = provider === "bitbucket" ? "username:app_password" : "paste token here";
    tokenHintEl.textContent = preset.tokenHint || "";
    const normalized = normalizeHost(hostEl.value);
    hostHintEl.textContent = `${preset.hostHint || ""} Saved as: ${normalized || "(empty)"}`;

    // If host is empty OR still equals the previous auto host, replace it with the new preset.
    const cur = hostEl.value.trim();
    if (!cur || (lastAutoHost && normalizeHost(cur) === normalizeHost(lastAutoHost))) {
      hostEl.value = preset.host && preset.host !== "gitea.yourcompany.com" ? preset.host : cur;
      lastAutoHost = hostEl.value;
      const n2 = normalizeHost(hostEl.value);
      hostHintEl.textContent = `${preset.hostHint || ""} Saved as: ${n2 || "(empty)"}`;
    }
  }

  providerEl.addEventListener("change", applyProviderPreset);
  hostEl.addEventListener("input", () => {
    const provider = providerEl.value;
    const preset = PROVIDER_PRESETS[provider] || {};
    const normalized = normalizeHost(hostEl.value);
    hostHintEl.textContent = `${preset.hostHint || ""} Saved as: ${normalized || "(empty)"}`;
  });

  tokenForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const provider = document.getElementById("provider").value;
      const hostRaw = normalizeHost(document.getElementById("host").value.trim());
      const token = document.getElementById("token").value.trim();
      const resp = await postJson("api/settings/token", { provider, host: hostRaw, token });
      document.getElementById("token").value = "";
      await refresh();
      toast("ok", "Token saved", `Provider: ${provider}\nHost: ${resp.host || hostRaw}`);
    } catch (err) {
      toast("err", "Failed to save token", err.message || "Unknown error");
    }
  });

  llmForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const provider = document.getElementById("llm-provider").value;
      await postJson("api/settings/llm", {
        provider,
        default_model: document.getElementById("default-model").value.trim() || null,
        openai_api_key: document.getElementById("openai-api-key").value.trim() || null,
        openai_endpoint: document.getElementById("openai-endpoint")?.value?.trim() || null,
        openai_api_version: document.getElementById("openai-api-version")?.value?.trim() || null,
        openai_deployment: document.getElementById("openai-deployment")?.value?.trim() || null,
      });
      document.getElementById("openai-api-key").value = "";
      await refresh();
      toast("ok", "LLM settings saved", "Your model provider settings were updated.");
    } catch (err) {
      toast("err", "Failed to save LLM settings", err.message || "Unknown error");
    }
  });

  llmClear.addEventListener("click", async () => {
    try {
      await postJson("api/settings/llm/clear", {});
      await refresh();
      toast("ok", "LLM settings cleared", "Heuristic mode will be used unless you configure an LLM again.");
    } catch (err) {
      toast("err", "Failed to clear LLM settings", err.message || "Unknown error");
    }
  });

  // LLM provider UI: show custom endpoint fields always (optional)

  applyProviderPreset();
  refresh();
});


