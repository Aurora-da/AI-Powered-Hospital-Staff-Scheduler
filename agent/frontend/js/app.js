const API_BASE = "/api";

const App = {
  currentPage: "dashboard",

  async init() {
    this.setupNavigation();
    this.setupSidebarToggle();
    this.renderDashboard();
  },

  // ===== Navigation =====
  setupNavigation() {
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        const page = el.dataset.page;
        this.navigate(page);
      });
    });
  },

  setupSidebarToggle() {
    const btn = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar");
    btn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
    document.addEventListener("click", (e) => {
      if (window.innerWidth <= 768) {
        if (!sidebar.contains(e.target) && !btn.contains(e.target)) {
          sidebar.classList.remove("open");
        }
      }
    });
  },

  navigate(page) {
    this.currentPage = page;
    // Update nav
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.page === page);
    });
    // Show page
    document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add("active");
    // Update title
    const names = {
      dashboard: "工作台",
      schedule: "排班管理",
      swap: "调班管理",
      conflicts: "冲突检测",
      emergency: "紧急代班",
      analytics: "数据分析",
      preferences: "偏好管理",
      chat: "AI 对话",
    };
    document.getElementById("pageTitle").textContent = names[page] || page;

    // Auto-load data for pages
    if (page === "dashboard") this.renderDashboard();
    if (page === "schedule") this.loadScheduleTable();
    if (page === "chat") this.scrollChatBottom();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
      document.getElementById("sidebar").classList.remove("open");
    }
  },

  // ===== API =====
  async apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
      headers: { "Content-Type": "application/json" },
      ...options,
    };
    const resp = await fetch(url, config);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    return resp.json();
  },

  // ===== Dashboard =====
  async renderDashboard() {
    const grid = document.getElementById("statsGrid");
    grid.innerHTML = `
      <div class="stat-card"><div class="stat-spinner"></div></div>
      <div class="stat-card"><div class="stat-spinner"></div></div>
      <div class="stat-card"><div class="stat-spinner"></div></div>
      <div class="stat-card"><div class="stat-spinner"></div></div>
    `;

    try {
      const [staff, shifts, schedule] = await Promise.all([
        this.apiFetch("/staff").catch(() => []),
        this.apiFetch("/shifts").catch(() => []),
        this.apiFetch("/schedule").catch(() => []),
      ]);

      grid.innerHTML = `
        <div class="stat-card">
          <div class="stat-value" style="color:var(--primary)">${staff.length}</div>
          <div class="stat-label">员工总数</div>
          <div class="stat-desc">可参与排班的医护人员</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--success)">${shifts.length}</div>
          <div class="stat-label">班次总数</div>
          <div class="stat-desc">当前排班周期内的班次</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--warning)">${schedule.length}</div>
          <div class="stat-label">已排班次</div>
          <div class="stat-desc">已安排的人员班次数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--info)">
            ${staff.length > 0 ? Math.round(schedule.length / staff.length) : 0}
          </div>
          <div class="stat-label">人均班次</div>
          <div class="stat-desc">平均每人排班次数</div>
        </div>
      `;

      // Preview table
      const preview = document.getElementById("dashboardPreview");
      if (schedule.length > 0) {
        preview.innerHTML = this.buildTable(schedule.slice(0, 15), [
          "staff", "date", "shift_type", "role",
        ]);
      } else {
        preview.innerHTML =
          '<p class="text-muted">暂无排班数据，前往「排班管理」生成排班表</p>';
      }
    } catch (e) {
      grid.innerHTML = `<div class="stat-card"><p class="text-danger">加载失败: ${e.message}</p></div>`;
    }
  },

  // ===== Schedule =====
  async loadScheduleTable() {
    const el = document.getElementById("scheduleTable");
    try {
      const data = await this.apiFetch("/schedule");
      if (data.length > 0) {
        el.innerHTML = this.buildTable(data, [
          "staff", "date", "shift_type", "role", "skill_level",
        ]);
      } else {
        el.innerHTML = '<p class="text-muted">暂无排班数据，请先生成排班</p>';
      }
    } catch (e) {
      el.innerHTML = `<p class="text-danger">加载失败: ${e.message}</p>`;
    }
  },

  async generateSchedule() {
    const btn = document.getElementById("genScheduleBtn");
    const result = document.getElementById("scheduleResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 生成中...';
    result.innerHTML = "";

    try {
      const resp = await this.apiFetch("/schedule/generate", { method: "POST" });
      result.innerHTML = `<div class="alert alert-success">排班生成成功！共 ${resp.data.length} 条记录</div>`;
      const table = document.getElementById("scheduleTable");
      table.innerHTML = this.buildTable(resp.data, [
        "staff", "date", "shift_type", "role", "skill_level",
      ]);
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
        生成排班
      `;
    }
  },

  // ===== Swap =====
  async handleSwap(e) {
    e.preventDefault();
    const form = e.target;
    const data = Object.fromEntries(new FormData(form));
    const result = document.getElementById("swapResult");
    result.innerHTML = '<p><span class="spinner"></span> 正在处理调班...</p>';

    try {
      const resp = await this.apiFetch("/schedule/swap", {
        method: "POST",
        body: JSON.stringify(data),
      });
      result.innerHTML = `<div class="alert alert-success">调班成功！</div>`;
      const logs = resp.logs || [];
      if (logs.length > 0) {
        result.innerHTML +=
          '<div class="report-box">' + logs.join("\n") + "</div>";
      }
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  },

  // ===== Conflicts =====
  async detectConflicts() {
    const btn = document.getElementById("conflictBtn");
    const result = document.getElementById("conflictResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 检测中...';
    result.innerHTML = "";

    try {
      const resp = await this.apiFetch("/conflicts");
      const report = resp.report || "检测完成，无冲突报告";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        开始检测
      `;
    }
  },

  // ===== Emergency =====
  async handleEmergency(e) {
    e.preventDefault();
    const form = e.target;
    const data = Object.fromEntries(new FormData(form));
    const result = document.getElementById("emergencyResult");
    result.innerHTML = '<p><span class="spinner"></span> 正在查找代班人员...</p>';

    try {
      const resp = await this.apiFetch("/emergency/substitute", {
        method: "POST",
        body: JSON.stringify(data),
      });
      const report = resp.report || "未找到合适代班人员";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  },

  // ===== Workload =====
  async loadWorkload() {
    const btn = document.getElementById("workloadBtn");
    const result = document.getElementById("workloadResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 分析中...';
    result.innerHTML = "";

    try {
      const resp = await this.apiFetch("/workload");
      const report = resp.report || "分析完成";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
        分析工作量
      `;
    }
  },

  // ===== Quality =====
  async loadQuality() {
    const btn = document.getElementById("qualityBtn");
    const result = document.getElementById("qualityResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 评估中...';
    result.innerHTML = "";

    try {
      const resp = await this.apiFetch("/quality");
      const report = resp.report || "评估完成";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        评估质量
      `;
    }
  },

  // ===== Preferences =====
  async handleLearnPref(e) {
    e.preventDefault();
    const form = e.target;
    const data = Object.fromEntries(new FormData(form));
    const result = document.getElementById("prefLearnResult");

    try {
      const resp = await this.apiFetch("/preferences/learn", {
        method: "POST",
        body: JSON.stringify(data),
      });
      const report = resp.report || "记录成功";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
      form.reset();
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  },

  async loadPreferences() {
    const result = document.getElementById("prefResult");
    result.innerHTML = '<p><span class="spinner"></span> 加载中...</p>';

    try {
      const resp = await this.apiFetch("/preferences");
      const report = resp.report || "暂无偏好记录";
      result.innerHTML = `<div class="report-box">${this.escapeHtml(report)}</div>`;
    } catch (e) {
      result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  },

  // ===== Chat =====
  async handleChat(e) {
    e.preventDefault();
    const form = e.target;
    const input = form.querySelector('input[name="message"]');
    const message = input.value.trim();
    if (!message) return;

    // Add user message
    this.addChatMessage(message, "user");
    input.value = "";
    this.scrollChatBottom();

    // Show typing indicator
    const typingId = this.addChatMessage("正在思考...", "ai typing");
    this.scrollChatBottom();

    try {
      const resp = await this.apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      });

      // Remove typing indicator
      const typing = document.getElementById(typingId);
      if (typing) typing.remove();

      if (resp.success) {
        this.addChatMessage(resp.response, "ai");
      } else {
        this.addChatMessage(resp.response || "处理失败，请重试", "ai");
      }
    } catch (e) {
      const typing = document.getElementById(typingId);
      if (typing) typing.remove();
      this.addChatMessage(`抱歉，出错了：${e.message}`, "ai");
    }
    this.scrollChatBottom();
  },

  addChatMessage(text, type) {
    const container = document.getElementById("chatMessages");
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const div = document.createElement("div");
    div.id = id;
    div.className = `chat-msg chat-msg-${type === "user" ? "user" : "ai"}`;
    div.innerHTML = `
      <div class="msg-avatar">${type === "user" ? "我" : "AI"}</div>
      <div class="msg-content"><p>${this.escapeHtml(text).replace(/\n/g, "<br>")}</p></div>
    `;
    if (type === "typing") div.classList.add("chat-msg-ai");
    container.appendChild(div);
    return id;
  },

  scrollChatBottom() {
    const container = document.getElementById("chatMessages");
    setTimeout(() => {
      container.scrollTop = container.scrollHeight;
    }, 50);
  },

  // ===== Helpers =====
  buildTable(data, columns) {
    if (!data || data.length === 0) return '<p class="text-muted">暂无数据</p>';
    const headers = {
      staff: "员工",
      date: "日期",
      shift_type: "班次类型",
      role: "角色",
      skill_level: "技能等级",
      staff_id: "员工ID",
      shift_id: "班次ID",
    };
    let html = "<table><thead><tr>";
    columns.forEach((col) => {
      html += `<th>${headers[col] || col}</th>`;
    });
    html += "</tr></thead><tbody>";
    data.forEach((row) => {
      html += "<tr>";
      columns.forEach((col) => {
        let val = row[col] ?? "-";
        if (col === "shift_type") {
          const tagMap = { 早班: "tag-blue", 中班: "tag-green", 夜班: "tag-purple" };
          const cls = tagMap[val] || "tag-blue";
          val = `<span class="tag ${cls}">${val}</span>`;
        } else if (col === "skill_level") {
          val = `<span class="tag tag-yellow">Lv.${val}</span>`;
        }
        html += `<td>${val}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    return html;
  },

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  },
};

// ===== Init =====
document.addEventListener("DOMContentLoaded", () => App.init());
