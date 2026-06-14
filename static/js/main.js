/**
 * main.js — CampusPulse client-side interactions
 * Features: mobile nav, scroll effects, file upload preview,
 *           char counters, upvote AJAX, chat bot simulation.
 */

/* ── Run after DOM is fully loaded ─────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initNavbar();
  initScrollEffect();
  initFileUpload();
  initCharCounters();
  initUpvoteButtons();
  initChatBot();
  initPromptChips();
  animateNumbers();
  initResolutionTimers();
});

/* ── 0. Light / Dark Theme Toggle ───────────────────────────── */
function initTheme() {
  const btn  = document.getElementById("themeToggle");
  const icon = document.getElementById("themeIcon");
  if (!btn) return;

  // Sync body class from localStorage (pre-light on html was set before paint)
  const saved = localStorage.getItem("cp-theme");
  document.documentElement.classList.remove("pre-light");
  if (saved === "light") {
    document.body.classList.add("light-theme");
    if (icon) icon.className = "ph ph-lightbulb-filament";
  } else {
    document.body.classList.remove("light-theme");
    if (icon) icon.className = "ph ph-lightbulb";
  }

  btn.addEventListener("click", () => {
    const isLight = document.body.classList.toggle("light-theme");
    localStorage.setItem("cp-theme", isLight ? "light" : "dark");
    if (icon) {
      icon.className = isLight ? "ph ph-lightbulb-filament" : "ph ph-lightbulb";
    }
  });
}

/* ── 1. Mobile Navbar Toggle ────────────────────────────────── */
function initNavbar() {
  const hamburger = document.getElementById("hamburger");
  const navLinks  = document.getElementById("navLinks");
  if (!hamburger || !navLinks) return;

  hamburger.addEventListener("click", () => {
    navLinks.classList.toggle("open");
    // Animate the hamburger icon
    hamburger.classList.toggle("active");
  });

  // Close menu when a link is clicked
  navLinks.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => navLinks.classList.remove("open"));
  });

  // Close when clicking outside
  document.addEventListener("click", (e) => {
    if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
      navLinks.classList.remove("open");
    }
  });
}

/* ── 2. Navbar shadow on scroll ─────────────────────────────── */
function initScrollEffect() {
  const navbar = document.getElementById("navbar");
  if (!navbar) return;

  window.addEventListener("scroll", () => {
    if (window.scrollY > 20) {
      navbar.style.boxShadow = "0 4px 30px rgba(0,0,0,0.4)";
    } else {
      navbar.style.boxShadow = "none";
    }
  });
}

/* ── 3. File Upload Preview ─────────────────────────────────── */
function initFileUpload() {
  const area        = document.getElementById("fileUploadArea");
  const input       = document.getElementById("image");
  const placeholder = document.getElementById("uploadPlaceholder");
  const preview     = document.getElementById("uploadPreview");
  const previewImg  = document.getElementById("previewImg");
  const removeBtn   = document.getElementById("removeImg");

  if (!area || !input) return;

  // Click on the area opens file picker
  area.addEventListener("click", (e) => {
    if (!removeBtn || !removeBtn.contains(e.target)) {
      input.click();
    }
  });

  // Drag & drop support
  area.addEventListener("dragover", (e) => {
    e.preventDefault();
    area.style.borderColor = "var(--accent)";
  });
  area.addEventListener("dragleave", () => {
    area.style.borderColor = "";
  });
  area.addEventListener("drop", (e) => {
    e.preventDefault();
    area.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file) showPreview(file);
  });

  input.addEventListener("change", () => {
    if (input.files[0]) showPreview(input.files[0]);
  });

  if (removeBtn) {
    removeBtn.addEventListener("click", () => {
      input.value = "";
      previewImg.src = "#";
      placeholder.classList.remove("hidden");
      preview.classList.add("hidden");
    });
  }

  function showPreview(file) {
    const allowed = ["image/png","image/jpeg","image/gif","image/webp"];
    if (!allowed.includes(file.type)) {
      showToast("Please upload a PNG, JPG, GIF, or WebP image.", "error");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast("File is too large. Maximum size is 5 MB.", "error");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      placeholder.classList.add("hidden");
      preview.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
  }
}

/* ── 4. Character Counters for Form Fields ───────────────────── */
function initCharCounters() {
  const pairs = [
    { input: "title",       counter: "titleCount",  max: 100 },
    { input: "description", counter: "descCount",   max: 1000 },
  ];

  pairs.forEach(({ input, counter, max }) => {
    const el  = document.getElementById(input);
    const cnt = document.getElementById(counter);
    if (!el || !cnt) return;

    const update = () => {
      const len = el.value.length;
      cnt.textContent = `${len} / ${max}`;
      cnt.style.color = len > max * 0.9 ? "var(--red)" : "var(--text-muted)";
    };

    el.addEventListener("input", update);
    update();
  });
}

/* ── 5. Upvote Buttons (AJAX) ────────────────────────────────── */
function initUpvoteButtons() {
  // Track which complaints this session has already upvoted
  const upvoted = new Set(JSON.parse(sessionStorage.getItem("upvoted") || "[]"));

  document.querySelectorAll(".upvote-btn").forEach(btn => {
    const id = btn.dataset.id;

    // Restore session state
    if (upvoted.has(id)) btn.classList.add("upvoted");

    btn.addEventListener("click", async () => {
      if (upvoted.has(id)) {
        showToast("You've already upvoted this issue.", "info");
        return;
      }

      try {
        const res  = await fetch(`/api/upvote/${id}`, { method: "POST" });
        const data = await res.json();
        if (data.upvotes !== undefined) {
          document.getElementById(`upvote-${id}`).textContent = data.upvotes;
          btn.classList.add("upvoted");
          upvoted.add(id);
          sessionStorage.setItem("upvoted", JSON.stringify([...upvoted]));
          showToast("Upvoted! Thanks for the feedback.", "success");
        }
      } catch {
        showToast("Could not process your upvote. Try again.", "error");
      }
    });
  });
}

/* ── 6. Chat Bot Simulation ──────────────────────────────────── */
function initChatBot() {
  const input    = document.getElementById("chatInput");
  const sendBtn  = document.getElementById("sendBtn");
  const messages = document.getElementById("chatMessages");
  const typing   = document.getElementById("typingIndicator");

  if (!input || !sendBtn) return;

  // Conversation history sent to backend for context
  const history = [];

  function appendMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `chat-msg chat-msg--${sender}`;

    const avatarDiv = document.createElement("div");
    avatarDiv.className = `chat-avatar ${sender === "bot" ? "bot-avatar" : "user-avatar"}`;
    avatarDiv.innerHTML = sender === "bot"
      ? `<i class="ph ph-robot"></i>`
      : `<i class="ph ph-user"></i>`;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    // Render **bold**, newlines, and emoji naturally
    const formatted = text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br>");
    bubble.innerHTML = `<p>${formatted}</p>`;

    div.appendChild(avatarDiv);
    div.appendChild(bubble);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function appendError(msg) {
    const div = document.createElement("div");
    div.className = "chat-msg chat-msg--bot";
    div.innerHTML = `
      <div class="chat-avatar bot-avatar"><i class="ph ph-robot"></i></div>
      <div class="chat-bubble" style="border-color:rgba(248,113,113,0.4);background:rgba(248,113,113,0.07);">
        <p style="color:#f87171;"><i class="ph ph-warning-circle"></i> ${msg}</p>
      </div>`;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    history.push({ role: "user", text });
    input.value = "";
    sendBtn.disabled = true;

    typing.classList.remove("hidden");
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await fetch("/api/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ message: text, history: history.slice(-10) })
      });

      const data = await res.json();
      typing.classList.add("hidden");

      if (data.reply) {
        appendMessage(data.reply, "bot");
        history.push({ role: "model", text: data.reply });
      } else {
        appendError(data.error || "Something went wrong. Please try again.");
      }
    } catch (err) {
      typing.classList.add("hidden");
      appendError("Couldn't reach NOVA. Check your internet connection.");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}

/* ── 7. Prompt Suggestion Chips ──────────────────────────────── */
function initPromptChips() {
  const chatInput = document.getElementById("chatInput");
  document.querySelectorAll(".prompt-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      if (chatInput) {
        chatInput.value = chip.dataset.prompt;
        chatInput.focus();
      }
    });
  });
}

/* ── 8. Animate stat numbers on homepage ─────────────────────── */
function animateNumbers() {
  document.querySelectorAll(".stat-num").forEach(el => {
    const target = parseInt(el.textContent, 10);
    if (isNaN(target) || target === 0) return;

    let current = 0;
    const step  = Math.max(1, Math.floor(target / 30));
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current;
      if (current >= target) clearInterval(timer);
    }, 30);
  });
}

/* ── Utility: Toast notifications ────────────────────────────── */
function showToast(message, type = "success") {
  const container = (() => {
    let c = document.querySelector(".flash-container");
    if (!c) {
      c = document.createElement("div");
      c.className = "flash-container";
      document.body.appendChild(c);
    }
    return c;
  })();

  const toast = document.createElement("div");
  toast.className = `flash flash-${type}`;
  const icon = type === "success" ? "check-circle"
             : type === "error"   ? "warning-circle"
             : "info";
  toast.innerHTML = `
    <i class="ph ph-${icon}"></i>
    ${message}
    <button class="flash-close" onclick="this.parentElement.remove()">×</button>
  `;

  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* ── Resolution Timer ────────────────────────────────────────── */
function initResolutionTimers() {
  const timers = document.querySelectorAll(".res-timer");
  if (!timers.length) return;

  function calcLabel(createdAt, status) {
    if (status === "Resolved") return null; // already handled in HTML
    const created = new Date(createdAt.replace(" ", "T"));
    if (isNaN(created)) return "—";
    const now     = new Date();
    const diffMs  = now - created;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr  = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1)   return "just now";
    if (diffMin < 60)  return `${diffMin}m ago`;
    if (diffHr  < 24)  return `${diffHr}h pending`;
    if (diffDay === 1) return "1 day pending";
    return `${diffDay} days pending`;
  }

  function urgencyClass(createdAt, status) {
    if (status === "Resolved") return "";
    const diffDay = Math.floor((new Date() - new Date(createdAt.replace(" ","T"))) / 86400000);
    if (diffDay >= 7)  return "res-timer--urgent";
    if (diffDay >= 3)  return "res-timer--warning";
    return "";
  }

  function updateAll() {
    timers.forEach(el => {
      const created = el.dataset.created;
      const status  = el.dataset.status;
      if (status === "Resolved") return;

      const label = el.querySelector(".timer-label");
      if (label) {
        label.textContent = calcLabel(created, status);
      }

      // Remove old urgency classes then re-apply
      el.classList.remove("res-timer--urgent", "res-timer--warning");
      const cls = urgencyClass(created, status);
      if (cls) el.classList.add(cls);
    });
  }

  updateAll();
  setInterval(updateAll, 60000); // refresh every minute
}
