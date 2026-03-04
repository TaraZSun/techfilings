/**
 * frontend/app.js
 * Handles chat state, API calls, and DOM rendering for TechFilings.
 */

// ── Config ──────────────────────────────────────────────────────────────────
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8001"
  : "https://your-railway-app.up.railway.app"; // replace with your Railway URL after deploy

// ── State ───────────────────────────────────────────────────────────────────
const state = {
  chatId: crypto.randomUUID(),
  cookieAccepted: null,
  messages: [],
  questionCount: 0,
  feedbackCount: 0,
  isLoading: false,
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const chatContainer   = document.getElementById("chat-container");
const inputEl         = document.getElementById("query-input");
const sendBtn         = document.getElementById("send-btn");
const cookieBanner    = document.getElementById("cookie-banner");
const acceptBtn       = document.getElementById("cookie-accept");
const declineBtn      = document.getElementById("cookie-decline");
const feedbackOverlay = document.getElementById("feedback-overlay");
const feedbackInput   = document.getElementById("feedback-input");
const feedbackSubmit  = document.getElementById("feedback-submit");
const wordCounter     = document.getElementById("word-counter");

// ── Cookie banner ─────────────────────────────────────────────────────────
acceptBtn.addEventListener("click", () => {
  state.cookieAccepted = true;
  cookieBanner.classList.add("hidden");
});

declineBtn.addEventListener("click", () => {
  state.cookieAccepted = false;
  cookieBanner.classList.add("hidden");
});

// ── Send message ──────────────────────────────────────────────────────────
sendBtn.addEventListener("click", handleSend);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

async function handleSend() {
  const question = inputEl.value.trim();
  if (!question || state.isLoading) return;

  if (needsFeedback()) {
    showFeedbackGate();
    return;
  }

  inputEl.value = "";
  state.isLoading = true;
  setInputDisabled(true);

  appendMessage("user", question);
  state.messages.push({ role: "user", content: question });

  const loadingEl = appendLoading();

  try {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        chat_id: state.chatId,
        cookie_accepted: state.cookieAccepted === true,
      }),
    });

    if (!res.ok) throw new Error(`API error ${res.status}`);
    const data = await res.json();

    loadingEl.remove();
    appendMessage("assistant", data.answer, data.citations);
    state.messages.push({ role: "assistant", content: data.answer });
    state.questionCount++;

    if (needsFeedback()) {
      showFeedbackGate();
    }

  } catch (err) {
    loadingEl.remove();
    appendError("Something went wrong. Please try again.");
    console.error(err);
  } finally {
    state.isLoading = false;
    setInputDisabled(false);
    inputEl.focus();
  }
}

// ── Feedback gate ─────────────────────────────────────────────────────────
function needsFeedback() {
  return (
    state.questionCount > 0 &&
    state.questionCount % 3 === 0 &&
    state.feedbackCount < state.questionCount / 3
  );
}

function showFeedbackGate() {
  feedbackOverlay.classList.remove("hidden");
  feedbackInput.value = "";
  wordCounter.textContent = "";
  feedbackSubmit.disabled = true;
  setInputDisabled(true);
}

function hideFeedbackGate() {
  feedbackOverlay.classList.add("hidden");
  setInputDisabled(false);
  inputEl.focus();
}

feedbackInput.addEventListener("input", () => {
  const words = feedbackInput.value.trim().split(/\s+/).filter(Boolean).length;
  const needed = Math.max(0, 10 - words);
  if (words === 0) {
    wordCounter.textContent = "";
    wordCounter.className = "word-counter";
  } else if (needed > 0) {
    wordCounter.textContent = `${needed} more word${needed > 1 ? "s" : ""} needed`;
    wordCounter.className = "word-counter pending";
  } else {
    wordCounter.textContent = "✓ Ready to submit";
    wordCounter.className = "word-counter ready";
  }
  feedbackSubmit.disabled = words < 10;
});

feedbackSubmit.addEventListener("click", async () => {
  const text = feedbackInput.value.trim();
  if (text.split(/\s+/).filter(Boolean).length < 10) return;

  try {
    await fetch(`${API_BASE}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: state.chatId,
        feedback_text: text,
        after_question_num: state.questionCount,
      }),
    });
  } catch (err) {
    console.error("Feedback save failed:", err);
  }

  state.feedbackCount++;
  hideFeedbackGate();
});

// ── DOM helpers ───────────────────────────────────────────────────────────
function appendMessage(role, content, citations = []) {
  const wrapper = document.createElement("div");
  wrapper.className = `message message-${role}`;

  if (role === "user") {
    wrapper.innerHTML = `<div class="bubble bubble-user">${escapeHtml(content)}</div>`;
  } else {
    const formatted = formatText(content);
    let citationsHtml = "";

    if (citations.length > 0) {
      const items = citations.map(c => {
        const section = c.section.length > 40 ? c.section.slice(0, 40) + "…" : c.section;
        return `
          <div class="citation-item">
            <div class="citation-label">[${c.index}] ${escapeHtml(c.company)} · ${escapeHtml(c.form_type)} · ${escapeHtml(section)}</div>
            <div class="citation-body">${escapeHtml(c.text)}</div>
          </div>`;
      }).join("");

      citationsHtml = `
        <div class="citations">
          <div class="citations-header">Sources</div>
          ${items}
        </div>`;
    }

    wrapper.innerHTML = `
      <div class="bubble bubble-assistant">
        <div class="answer-text">${formatted}</div>
        ${citationsHtml}
      </div>`;
  }

  chatContainer.appendChild(wrapper);
  requestAnimationFrame(() => {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  });
  return wrapper;
}

function appendLoading() {
  const el = document.createElement("div");
  el.className = "message message-assistant";
  el.innerHTML = `
    <div class="bubble bubble-assistant loading">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </div>`;
  chatContainer.appendChild(el);
  requestAnimationFrame(() => {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  });
  return el;
}

function appendError(msg) {
  const el = document.createElement("div");
  el.className = "message message-error";
  el.innerHTML = `<div class="error-text">${escapeHtml(msg)}</div>`;
  chatContainer.appendChild(el);
}

function setInputDisabled(disabled) {
  inputEl.disabled = disabled;
  sendBtn.disabled = disabled;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatText(text) {
  return marked.parse(text);
}

// ── Citation toggle ────────────────────────────────────────────────────────
document.addEventListener("click", (e) => {
  const label = e.target.closest(".citation-label");
  if (label) {
    label.closest(".citation-item").classList.toggle("open");
  }
});