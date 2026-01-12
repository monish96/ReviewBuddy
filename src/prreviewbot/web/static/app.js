async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail?.error ? data.detail : data;
    const err = new Error(detail?.error || `Request failed (${res.status})`);
    err.detail = detail;
    err.status = res.status;
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

function toast(kind, title, msg) {
  const wrap = ensureToastWrap();
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="t-title">${escapeHtml(title)}</div><div class="t-msg">${escapeHtml(msg)}</div>`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), kind === "err" ? 7000 : 3500);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderResult(data) {
  // Some models return JSON-in-markdown fences; try to parse for better UX.
  const normalized = normalizeModelPayload(data);
  const header = `
    <div class="row" style="align-items:center">
      <span class="pill">Language: ${escapeHtml(normalized.language)}</span>
      <span class="pill">Model: ${escapeHtml(normalized.model)}</span>
    </div>
  `;

  const summaryHtml = renderSummary(normalized.summary);
  const grouped = groupComments(normalized.comments || []);
  const suggestionsHtml = renderGroupedComments(grouped);

  const actions = `
    <div class="result-actions">
      <button class="mini-btn" id="copy-md" type="button">Copy markdown</button>
    </div>
  `;

  const out = `
    ${header}
    ${actions}
    <div class="card" style="margin-top:10px">
      <h3 style="margin:0 0 8px 0">Summary</h3>
      ${summaryHtml}
    </div>
    <div style="margin-top:14px">
      <h3 style="margin:0 0 10px 0">Suggestions</h3>
      ${suggestionsHtml}
    </div>
  `;

  // Attach handler after render
  setTimeout(() => {
    const btn = document.getElementById("copy-md");
    if (btn) {
      btn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(toMarkdown(normalized));
          toast("ok", "Copied", "Copied review as markdown.");
        } catch (e) {
          toast("err", "Copy failed", String(e || "Unable to copy"));
        }
      };
    }
  }, 0);

  return out;
}

function normalizeModelPayload(data) {
  let summary = data.summary || "";
  let comments = data.comments || [];

  // If summary looks like a fenced JSON blob, parse it and override summary/comments
  const parsed = tryParseJsonFromText(summary);
  if (parsed && (parsed.summary || parsed.comments)) {
    summary = parsed.summary ?? summary;
    comments = parsed.comments ?? comments;
  }

  // Normalize summary arrays into bullet string
  if (Array.isArray(summary)) {
    summary = summary.map((x) => `- ${String(x).trim()}`).join("\n");
  }

  // Normalize comments if they are embedded in JSON string
  if (typeof comments === "string") {
    const pc = tryParseJsonFromText(comments);
    if (pc && Array.isArray(pc)) comments = pc;
  }

  return {
    pr_url: data.pr_url,
    language: data.language || "general",
    model: data.model || "heuristic",
    summary,
    comments: Array.isArray(comments) ? comments : [],
  };
}

function tryParseJsonFromText(text) {
  if (!text) return null;
  let t = String(text).trim();
  if (t.startsWith("```")) {
    const parts = t.split("```");
    if (parts.length >= 3) t = parts[1];
    t = t.trim();
  }
  if (t.toLowerCase().startsWith("json\n")) t = t.slice(5).trim();
  if (!t.startsWith("{") && !t.startsWith("[")) return null;
  try {
    return JSON.parse(t);
  } catch {
    return null;
  }
}

function renderSummary(summary) {
  const s = String(summary || "").trim();
  if (!s) return `<div class="muted">No summary.</div>`;
  const lines = s.split("\n").map((l) => l.trim()).filter(Boolean);
  const bullets = lines.filter((l) => l.startsWith("- "));
  if (bullets.length) {
    return `<ul style="margin:0; padding-left:18px">${bullets
      .map((b) => `<li>${escapeHtml(b.replace(/^-\\s+/, ""))}</li>`)
      .join("")}</ul>`;
  }
  return `<div style="white-space:pre-wrap; overflow-wrap:anywhere">${escapeHtml(s)}</div>`;
}

function groupComments(comments) {
  const byFile = new Map();
  for (const c of comments || []) {
    const fp = c.file_path || "(general)";
    if (!byFile.has(fp)) byFile.set(fp, []);
    byFile.get(fp).push(c);
  }
  return Array.from(byFile.entries())
    .map(([file, items]) => ({ file, items }))
    .sort((a, b) => a.file.localeCompare(b.file));
}

function sevRank(s) {
  const v = String(s || "info").toLowerCase();
  if (v === "error") return 3;
  if (v === "warn" || v === "warning") return 2;
  return 1;
}

function renderGroupedComments(groups) {
  if (!groups.length) return `<div class="muted">No suggestions generated.</div>`;
  return groups
    .map((g) => {
      const itemsAll = (g.items || []).slice().sort((a, b) => sevRank(b.severity) - sevRank(a.severity));
      const items = itemsAll.filter((c) => sevRank(c.severity) >= 2);
      const infos = itemsAll.filter((c) => sevRank(c.severity) < 2);
      const counts = { error: 0, warn: 0, info: 0 };
      for (const it of itemsAll) {
        const k = String(it.severity || "info").toLowerCase();
        if (k.startsWith("err")) counts.error++;
        else if (k.startsWith("warn")) counts.warn++;
        else counts.info++;
      }
      const badge = `${counts.error ? `${counts.error} error` : ""}${counts.warn ? `${counts.warn} warn` : ""}${counts.info ? `${counts.info} info` : ""}`.trim();
      const rows = items
        .map((c) => {
          const sev = String(c.severity || "info").toLowerCase();
          const msg = c.message || "";
          const sugg = c.suggestion || "";
          const code = c.code_example || "";
          return `
            <div class="comment-row">
              <div class="row" style="align-items:center; gap:10px">
                <span class="sev ${escapeHtml(sev)}">${escapeHtml(sev.toUpperCase())}</span>
                ${c.start_line && c.end_line ? `<span class="pill">L${escapeHtml(String(c.start_line))}–L${escapeHtml(String(c.end_line))}</span>` : ``}
                ${c.related_url ? `<a class="link" style="margin-left:6px" href="${escapeHtml(c.related_url)}" target="_blank" rel="noreferrer">context</a>` : ``}
                <div style="margin-left:auto; display:flex; gap:8px; flex-wrap:wrap">
                  <button class="mini-btn post-btn" type="button"
                    data-file="${escapeHtml(c.file_path || "")}"
                    data-sev="${escapeHtml(sev)}"
                    data-msg="${escapeHtml(msg)}"
                    data-sugg="${escapeHtml(sugg)}"
                    data-code="${escapeHtml(code)}"
                    data-start="${escapeHtml(String(c.start_line || ""))}"
                    data-end="${escapeHtml(String(c.end_line || ""))}"
                    data-related="${escapeHtml(String(c.related_url || ""))}"
                  >Post to PR</button>
                </div>
              </div>
              <div class="comment-msg">${escapeHtml(msg)}</div>
              ${sugg ? `<div class="comment-sugg"><b>Suggestion:</b> ${escapeHtml(sugg)}</div>` : ""}
              ${code ? `<pre class="pre" style="margin-top:10px">${escapeHtml(stripFences(code))}</pre>` : ""}
            </div>
          `;
        })
        .join("");

      const infoRows = infos.length
        ? `
          <details class="file-group" style="margin-top:12px">
            <summary>
              <span class="file-path">Info (low priority)</span>
              <span class="muted">${infos.length} info</span>
            </summary>
            <div class="group-body">
              ${infos
                .map((c) => {
                  const sev = String(c.severity || "info").toLowerCase();
                  const msg = c.message || "";
                  const sugg = c.suggestion || "";
                  const code = c.code_example || "";
                  return `
                    <div class="comment-row">
                      <div class="row" style="align-items:center; gap:10px">
                        <span class="sev ${escapeHtml(sev)}">${escapeHtml(sev.toUpperCase())}</span>
                        <div style="margin-left:auto; display:flex; gap:8px; flex-wrap:wrap">
                          <button class="mini-btn post-btn" type="button"
                            data-file="${escapeHtml(c.file_path || "")}"
                            data-sev="${escapeHtml(sev)}"
                            data-msg="${escapeHtml(msg)}"
                            data-sugg="${escapeHtml(sugg)}"
                            data-code="${escapeHtml(code)}"
                            data-start="${escapeHtml(String(c.start_line || ""))}"
                            data-end="${escapeHtml(String(c.end_line || ""))}"
                            data-related="${escapeHtml(String(c.related_url || ""))}"
                          >Post to PR</button>
                        </div>
                      </div>
                      <div class="comment-msg">${escapeHtml(msg)}</div>
                      ${sugg ? `<div class="comment-sugg"><b>Suggestion:</b> ${escapeHtml(sugg)}</div>` : ""}
                      ${code ? `<pre class="pre" style="margin-top:10px">${escapeHtml(stripFences(code))}</pre>` : ""}
                    </div>
                  `;
                })
                .join("")}
            </div>
          </details>
        `
        : "";

      return `
        <details class="file-group" ${g.file === "(general)" ? "open" : ""}>
          <summary>
            <span class="file-path">${escapeHtml(g.file)}</span>
            <span class="muted">${escapeHtml(badge)}</span>
          </summary>
          <div class="group-body">${rows || `<div class="muted">No warn/error suggestions for this file.</div>`}${infoRows}</div>
        </details>
      `;
    })
    .join("");
}

function stripFences(code) {
  let t = String(code || "").trim();
  if (t.startsWith("```")) {
    const parts = t.split("```");
    if (parts.length >= 3) t = parts[1];
    t = t.trim();
    if (t.toLowerCase().startsWith("json\n")) t = t.slice(5).trim();
  }
  return t;
}

function toMarkdown(data) {
  const lines = [];
  lines.push("## PR Review");
  if (data.pr_url) lines.push(`- **PR**: ${data.pr_url}`);
  lines.push(`- **Language**: ${data.language}`);
  lines.push(`- **Model**: ${data.model}`);
  lines.push("");
  lines.push("### Summary");
  const s = String(data.summary || "").trim();
  lines.push(s || "- No summary.");
  lines.push("");
  lines.push("### Suggestions");
  if (!data.comments || !data.comments.length) {
    lines.push("- No suggestions generated.");
    return lines.join("\n");
  }
  for (const c of data.comments) {
    const loc = c.file_path ? `\`${c.file_path}\`: ` : "";
    const sev = String(c.severity || "info").toUpperCase();
    lines.push(`- **${sev}** ${loc}${String(c.message || "").trim()}`);
    if (c.suggestion) lines.push(`  - Suggestion: ${String(c.suggestion).trim()}`);
  }
  return lines.join("\n");
}

const STORAGE_KEY = "prreviewbot.tool.v1";

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function saveState(patch) {
  const cur = loadState();
  const next = { ...cur, ...patch };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

function clearState() {
  localStorage.removeItem(STORAGE_KEY);
}

window.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("review-form");
  const prLink = document.getElementById("pr-link");
  const language = document.getElementById("language");
  const llmProvider = document.getElementById("llm-provider");
  const llmModel = document.getElementById("llm-model");
  const resetBtn = document.getElementById("reset");
  const status = document.getElementById("status");
  const result = document.getElementById("result");

  // Restore persisted inputs (so going to Settings and back doesn't lose work)
  const st = loadState();
  if (st.pr_link) prLink.value = st.pr_link;
  if (st.language !== undefined) language.value = st.language;
  if (st.llm_provider !== undefined) llmProvider.value = st.llm_provider;
  if (st.llm_model) llmModel.value = st.llm_model;

  function persist() {
    saveState({
      pr_link: prLink.value.trim(),
      language: language.value || "",
      llm_provider: llmProvider.value || "",
      llm_model: llmModel.value.trim(),
    });
  }
  prLink.addEventListener("input", persist);
  language.addEventListener("change", persist);
  llmProvider.addEventListener("change", persist);
  llmModel.addEventListener("input", persist);

  resetBtn.addEventListener("click", () => {
    clearState();
    prLink.value = "";
    language.value = "";
    llmProvider.value = "";
    llmModel.value = "";
    status.textContent = "";
    result.innerHTML = "";
    toast("ok", "Reset", "Cleared inputs and saved state.");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.textContent = "Reviewing…";
    result.innerHTML = "";
    persist();
    try {
      const data = await postJson("api/review", {
        pr_link: prLink.value.trim(),
        language: language.value || null,
        llm_provider: llmProvider.value || null,
        llm_model: llmModel.value.trim() || null,
      });
      status.textContent = "Done.";
      result.innerHTML = renderResult(data);
      toast("ok", "Review complete", `Language: ${data.language}\nModel: ${data.model}`);

      // Wire post buttons
      document.querySelectorAll(".post-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const msg = btn.getAttribute("data-msg") || "";
          const sev = btn.getAttribute("data-sev") || "info";
          const file = btn.getAttribute("data-file") || null;
          const sugg = btn.getAttribute("data-sugg") || null;
          const code = btn.getAttribute("data-code") || null;
          const start = parseInt(btn.getAttribute("data-start") || "", 10);
          const end = parseInt(btn.getAttribute("data-end") || "", 10);
          const related = btn.getAttribute("data-related") || null;
          try {
            const resp = await postJson("api/pr/comment", {
              pr_link: prLink.value.trim(),
              file_path: file || null,
              severity: sev,
              message: msg,
              suggestion: sugg || null,
              code_example: code || null,
              start_line: Number.isFinite(start) ? start : null,
              end_line: Number.isFinite(end) ? end : null,
              related_url: related || null,
            });
            toast("ok", "Comment posted", resp.comment_url ? `Posted: ${resp.comment_url}` : "Posted.");
          } catch (err) {
            const detail = err.detail || {};
            if (err.status === 401 && detail.settings_url) {
              toast("err", "Auth required", `${detail.provider} on ${detail.host}\nAdd token in Settings.`);
            } else {
              toast("err", "Failed to post comment", err.message || "Unknown error");
            }
          }
        });
      });
    } catch (err) {
      const detail = err.detail || {};
      if (err.status === 401 && detail.settings_url) {
        status.innerHTML = `Auth required for <b>${escapeHtml(detail.provider)}</b> on <code>${escapeHtml(detail.host)}</code>. Go to <a href="${escapeHtml(detail.settings_url)}">Settings</a>.`;
        toast("err", "Authentication required", `${detail.provider} on ${detail.host}\nAdd a token in Settings and retry.`);
      } else {
        status.textContent = err.message || "Error";
        toast("err", "Review failed", err.message || "Unknown error");
      }
    }
  });
});


