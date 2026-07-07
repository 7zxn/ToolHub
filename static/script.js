(function () {
  "use strict";

  const form = document.getElementById("search-form");
  const input = document.getElementById("username-input");
  const searchBtn = document.getElementById("search-btn");
  const statusArea = document.getElementById("status-area");
  const loadingEl = document.getElementById("loading");
  const loadingText = loadingEl.querySelector("span:last-child");
  const summaryEl = document.getElementById("summary");
  const errorBox = document.getElementById("error-box");
  const resultsEl = document.getElementById("results");
  const subtitleEl = document.getElementById("subtitle");

  const dropdown = document.querySelector(".tool-dropdown");
  const dropdownBtn = document.getElementById("tool-dropdown-btn");
  const dropdownLabel = document.getElementById("tool-dropdown-label");
  const dropdownMenu = document.getElementById("tool-dropdown-menu");
  const toolOptions = Array.from(dropdownMenu.querySelectorAll(".tool-option"));

  const TOOLS = {
    sherlock: {
      label: "Sherlock",
      endpoint: "/api/search",
      placeholder: "أدخل اسم المستخدم...",
      subtitle: "ابحث عن اسم مستخدم عبر مئات المواقع الاجتماعية",
      loadingText: "جاري البحث...",
      emptyText: "لم يتم العثور على أي حساب بهذا الاسم.",
      buildQuery: (value) => ({ username: value }),
      invalidMessage: "الرجاء إدخال اسم مستخدم.",
      resultType: "profile",
    },
    photon: {
      label: "Photon",
      endpoint: "/api/photon",
      placeholder: "أدخل رابط الموقع (example.com)...",
      subtitle: "افحص موقعًا واستخرج الروابط والبيانات المهمة منه",
      loadingText: "جاري الفحص...",
      emptyText: "لم يتم العثور على أي نتائج لهذا الرابط.",
      buildQuery: (value) => ({ url: value }),
      invalidMessage: "الرجاء إدخال رابط صالح.",
      resultType: "photon",
    },
    maigret: {
      label: "Maigret",
      endpoint: "/api/maigret",
      placeholder: "أدخل اسم المستخدم...",
      subtitle: "بحث موسّع عن اسم مستخدم مع تفاصيل إضافية عبر المواقع",
      loadingText: "جاري البحث...",
      emptyText: "لم يتم العثور على أي حساب بهذا الاسم.",
      buildQuery: (value) => ({ username: value }),
      invalidMessage: "الرجاء إدخال اسم مستخدم.",
      resultType: "profile",
    },
  };

  let currentTool = "sherlock";

  function closeDropdown() {
    dropdown.classList.remove("open");
    dropdownMenu.hidden = true;
    dropdownBtn.setAttribute("aria-expanded", "false");
  }

  function openDropdown() {
    dropdown.classList.add("open");
    dropdownMenu.hidden = false;
    dropdownBtn.setAttribute("aria-expanded", "true");
  }

  function toggleDropdown() {
    if (dropdownMenu.hidden) {
      openDropdown();
    } else {
      closeDropdown();
    }
  }

  function setTool(toolName) {
    currentTool = toolName;
    const config = TOOLS[toolName];

    dropdownLabel.textContent = config.label;

    toolOptions.forEach((option) => {
      const isActive = option.dataset.tool === toolName;
      option.classList.toggle("active", isActive);
      option.setAttribute("aria-selected", String(isActive));
    });

    input.placeholder = config.placeholder;
    subtitleEl.textContent = config.subtitle;
    input.value = "";
    resetStatus();
    resultsEl.innerHTML = "";
    closeDropdown();
  }

  function resetStatus() {
    statusArea.hidden = true;
    loadingEl.hidden = true;
    summaryEl.hidden = true;
    errorBox.hidden = true;
    summaryEl.textContent = "";
    errorBox.textContent = "";
  }

  function showLoading() {
    resetStatus();
    statusArea.hidden = false;
    loadingEl.hidden = false;
    loadingText.textContent = TOOLS[currentTool].loadingText;
    resultsEl.innerHTML = "";
  }

  function showError(message) {
    resetStatus();
    statusArea.hidden = false;
    errorBox.hidden = false;
    errorBox.textContent = message;
  }

  function showSummary(count) {
    resetStatus();
    statusArea.hidden = false;
    summaryEl.hidden = false;
    summaryEl.textContent = `تم العثور على ${count} ${currentTool === "photon" ? "نتيجة" : "حساب"}.`;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function looksLikeUrl(value) {
    return /^https?:\/\//i.test(value);
  }

  function renderProfileResults(results) {
    const fragment = document.createDocumentFragment();

    results.forEach((item, index) => {
      const card = document.createElement("article");
      card.className = "result-card";
      card.style.animationDelay = `${Math.min(index * 25, 400)}ms`;

      card.innerHTML = `
        <div class="result-header">
          <span class="result-site">${escapeHtml(item.site)}</span>
          <span class="check-icon" aria-label="موجود">&#10004;</span>
        </div>
        <span class="result-url">${escapeHtml(item.url)}</span>
        <a class="result-open-btn" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">فتح الرابط</a>
      `;

      fragment.appendChild(card);
    });

    resultsEl.appendChild(fragment);
  }

  function renderPhotonResults(results) {
    const fragment = document.createDocumentFragment();

    results.forEach((item, index) => {
      const card = document.createElement("article");
      card.className = "result-card";
      card.style.animationDelay = `${Math.min(index * 25, 400)}ms`;

      const openButton = looksLikeUrl(item.value)
        ? `<a class="result-open-btn" href="${escapeHtml(item.value)}" target="_blank" rel="noopener noreferrer">فتح الرابط</a>`
        : "";

      card.innerHTML = `
        <div class="result-header">
          <span class="result-site">${escapeHtml(item.category)}</span>
          <span class="check-icon" aria-label="موجود">&#10004;</span>
        </div>
        <span class="result-url">${escapeHtml(item.value)}</span>
        ${openButton}
      `;

      fragment.appendChild(card);
    });

    resultsEl.appendChild(fragment);
  }

  function renderResults(results) {
    resultsEl.innerHTML = "";

    if (!results || results.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = TOOLS[currentTool].emptyText;
      resultsEl.appendChild(empty);
      return;
    }

    if (TOOLS[currentTool].resultType === "photon") {
      renderPhotonResults(results);
    } else {
      renderProfileResults(results);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const config = TOOLS[currentTool];
    const value = input.value.trim();
    if (!value) {
      showError(config.invalidMessage);
      return;
    }

    searchBtn.disabled = true;
    showLoading();

    try {
      const response = await fetch(config.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config.buildQuery(value)),
      });

      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        throw new Error("تعذر قراءة استجابة الخادم.");
      }

      if (!response.ok) {
        const message =
          (data && (data.detail || data.error)) ||
          "حدث خطأ غير متوقع أثناء البحث.";
        throw new Error(
          typeof message === "string" ? message : JSON.stringify(message)
        );
      }

      showSummary(data.total_found || 0);
      renderResults(data.results || []);
    } catch (err) {
      showError(err.message || "حدث خطأ غير متوقع. حاول مرة أخرى.");
      resultsEl.innerHTML = "";
    } finally {
      searchBtn.disabled = false;
    }
  }

  dropdownBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleDropdown();
  });

  toolOptions.forEach((option) => {
    option.addEventListener("click", () => setTool(option.dataset.tool));
  });

  document.addEventListener("click", (event) => {
    if (!dropdown.contains(event.target)) {
      closeDropdown();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDropdown();
    }
  });

  form.addEventListener("submit", handleSubmit);
})();
