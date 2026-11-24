(function () {
  "use strict";

  var I18N = {
    en: {
      hero_title: "The Complete AI Engineering & Autonomous Bot QA Suite for Minecraft",
      hero_lead: "Build, audit, deploy over SFTP & headless 2FA hosting panels, spawn resource-optimized headless test bots that auto-register/login and return off-screen PNG visual snapshots directly into your AI chat, and orchestrate all 10 SalyVn open-source Minecraft CLI tools from one MCP server.",
      cta_install: "Quick MCP Install",
      cta_calc: "Bot RAM Optimizer",
      stat_mcp: "Stdio MCP Tools (with PNG Image Output)",
      stat_bot: "RAM per Tier-1 Headless Bot (98% lighter)",
      stat_skills: "/mc:* Skills for Claude, Cursor & Codex",
      stat_suite: "Integrated SalyVn Minecraft Toolchain Repos",
      pipe_title: "5-Phase Autonomous Server & Plugin QA Pipeline",
      pipe_desc: "Click any phase below to inspect the exact MCP tool, safety guarantees, and outputs returned directly to your main chat.",
      calc_title: "Why 10 Desktop Minecraft Tabs Explode Your PC — And How MinecraftKit Fixes It",
      calc_desc: "Simulate your bot fleet below. MinecraftKit splits load across ~42 MB headless protocol bots and optional off-screen Docker/Xvfb visual containers.",
      calc_bots_lbl: "Concurrent Test Bots",
      calc_ram_lbl: "Host RAM Budget",
      calc_visual_lbl: "Needs Shader / Resource Pack 3D Visual Capture (enables 1 Docker/Xvfb client + N-1 Protocol bots)",
      calc_bars_title: "Estimated RAM Footprint Comparison",
      sim_title: "Interactive Autonomous Bot Stage Simulator",
      sim_desc: "Preview how MinecraftKit auto-detects AuthMe/nLogin prompts, redacts passwords, verifies custom GUIs, and streams a visual HUD snapshot back to chat.",
      ops_title: "End-to-End Server Operations Without Touching Your Screen",
      suite_title: "All 10 Integrated SalyVn Minecraft Open-Source Tools",
      suite_desc: "Filter by category to explore every integrated static analyzer, server matrix runner, shader validator, and resource pack compiler.",
      cfg_title: "1-Click MCP & Agent Skill Configuration"
    },
    vi: {
      hero_title: "Bộ Công Cụ AI, Bot Kiểm Thử Tự Động & Hệ Sinh Thái Toàn Diện Cho Minecraft",
      hero_lead: "Lập trình, kiểm tra tĩnh, tự kết nối Hosting/VPS có 2FA & SFTP không chiếm màn hình, tự gọi bot siêu nhẹ (~42 MB RAM) tự đăng ký/đăng nhập, test tính năng theo stages, chụp ảnh PNG gửi thẳng về khung chat AI và tích hợp toàn bộ 10 repo Minecraft của SalyVn.",
      cta_install: "Cài Đặt MCP Nhanh",
      cta_calc: "Tính Toán Tối Ưu RAM Bot",
      stat_mcp: "Công cụ MCP (trả ảnh PNG trực tiếp)",
      stat_bot: "RAM mỗi Bot Protocol không mở app MC",
      stat_skills: "Skill /mc:* cho Claude, Cursor & Codex",
      stat_suite: "Repo Minecraft SalyVn đã tích hợp",
      pipe_title: "Quy Trình Kiểm Thử Máy Chủ & Plugin Tự Động 5 Giai Đoạn",
      pipe_desc: "Chọn từng bước để xem công cụ MCP, cơ chế bảo vệ bí mật và dữ liệu kiểm thử trả về đoạn chat chính.",
      calc_title: "Vì Sao Mở 10 Tab Minecraft Sẽ Nổ Máy — Và Cách MinecraftKit Tối Ưu",
      calc_desc: "Kéo thanh trượt bên dưới để xem mức tiết kiệm RAM khi dùng Bot Protocol (~42 MB) kết hợp Docker/Xvfb chạy ngầm không chiếm màn hình.",
      calc_bots_lbl: "Số lượng Bot kiểm thử đồng thời",
      calc_ram_lbl: "Dung lượng RAM máy chủ / PC",
      calc_visual_lbl: "Cần test hiển thị Shader / Resource Pack 3D (chạy 1 Docker Xvfb + N-1 Bot Protocol)",
      calc_bars_title: "So Sánh Mức Tiêu Thụ RAM Ước Tính",
      sim_title: "Mô Phỏng Bot Chạy Stages & Chụp Ảnh HUD Gửi Về Chat",
      sim_desc: "Xem cách bot tự nhận diện AuthMe/nLogin, ẩn mật khẩu tự động, bấm kiểm tra GUI và xuất ảnh chụp trạng thái không chiếm chuột/màn hình.",
      ops_title: "Vận Hành Hosting, VPS 2FA, SFTP & Plugin Hỗ Trợ Test",
      suite_title: "Trọn Bộ 10 Repo Công Cụ Minecraft SalyVn Đã Tích Hợp",
      suite_desc: "Lọc theo nhóm chức năng để xem lệnh CLI & MCP của mcstage, shadersmith, packmigrate, pluginscope, serverdoctor, foliascan...",
      cfg_title: "Cấu Hình MCP & Cài Đặt Skill Chỉ Với 1 Lần Sao Chép"
    }
  };

  var PIPELINE = [
    {
      step: "PHASE 01",
      name: "Resource & Fleet Plan",
      tool: "mc_bot_plan_resources",
      desc: "Calculates safe bot concurrency and RAM caps before spawning anything. Recommends Tier-1 headless protocol bots (~42 MB each) or Hybrid 1 Docker/Xvfb Visual + N-1 Protocol.",
      sample: "strategy: hybrid-1-visual-plus-protocol | RAM saved vs desktop tabs: 93.2% | screen_lock_free: true"
    },
    {
      step: "PHASE 02",
      name: "Static & Pack Audits",
      tool: "mc_suite_orchestrate",
      desc: "Runs pluginscope (API & shading), foliascan (Folia thread-safety), shadersmith (GLSL std140 & 26.3), packmigrate (CustomModelData), and glyphsmith (bitmap fonts) with unified SARIF.",
      sample: "pluginscope + foliascan + shadersmith + packmigrate + glyphsmith -> 0 critical findings"
    },
    {
      step: "PHASE 03",
      name: "Headless Deploy / Boot",
      tool: "mc_sftp_operations + mc_hosting_server_action",
      desc: "Atomically uploads the built JAR over SFTP (.tmp -> SHA-256 -> rename), restarts via headless Pterodactyl/Pelican/Crafty API (with RFC 6238 TOTP 2FA), or boots a local mcstage matrix.",
      sample: "sftp://mcdev@192.0.2.10/plugins/MyRPG.jar (atomic swap) -> panel restart (headless 2FA)"
    },
    {
      step: "PHASE 04",
      name: "Autonomous Bot Stages",
      tool: "mc_bot_run_stages",
      desc: "Spawns screen-lock-free bot(s) that auto-detect /register or /login prompts (password redacted), accept resource packs, execute commands/GUI clicks, and verify chat/scoreboard/TPS assertions.",
      sample: "6/6 stages PASSED | auth_state: AUTHENTICATED | [REDACTED_PASSWORD] | 1 PNG snapshot attached"
    },
    {
      step: "PHASE 05",
      name: "Visual Proof & Triage",
      tool: "mc_bridge_plugin_query + mc_diagnose_server_log",
      desc: "Returns the rendered PNG HUD/GUI/Minimap snapshot directly inside the AI chat alongside mckit-bridge-plugin SEVERE error ring-buffer traces and serverdoctor fixes.",
      sample: "MCP content: [text/json, image/png (960x580)] -> instant visual verification & root-cause patch"
    }
  ];

  var PRESETS = [
    {
      id: "auth-shop",
      label: "AuthMe + RPG /shop GUI",
      header: "MCKitTester @ play.salyvn.net:25565 (42 MB RAM)",
      badge: "6/6 PASSED",
      stages: [
        ["Join Paper 26.3 Server", "PASS"],
        ["Auto-Detect & /register [REDACTED]", "PASS"],
        ["Accept Server Resource Pack", "PASS"],
        ["Execute /shop & Inspect 9x4 GUI", "PASS"],
        ["Assert Slot #13 Mythic Blade Lore", "PASS"],
        ["Render Off-Screen PNG to Chat", "PASS"]
      ],
      slots: { 4: "INFO", 11: "POTION", 13: "BLADE*", 15: "SHIELD", 22: "CLOSE" },
      chat: [
        "[Server] MCKitTester joined the game",
        "[AuthMe] Vui long /register <pass> <pass>",
        "[Bot] /register [REDACTED_PASSWORD] [REDACTED_PASSWORD]",
        "[AuthMe] Dang ky & dang nhap thanh cong!",
        "[Shop] Opened RPG Shop (5 populated slots)",
        "[MCKit] PNG snapshot attached to MCP chat"
      ]
    },
    {
      id: "folia-stress",
      label: "10-Bot Folia Region Stress",
      header: "MCKitPool (10x Protocol Bots · 420 MB Total)",
      badge: "TPS 19.9",
      stages: [
        ["Budget Check (420 MB vs 26 GB Desktop)", "PASS"],
        ["Stagger Spawn 10 Headless Bots", "PASS"],
        ["Teleport Across 4 Disjoint Regions", "PASS"],
        ["Run /guild war & /dungeon enter", "PASS"],
        ["Bridge Plugin Check: 0 Region Errors", "PASS"],
        ["Capture Multi-Region Telemetry Card", "PASS"]
      ],
      slots: { 0: "SWORD", 1: "BOW", 2: "PEARL", 8: "MAP" },
      chat: [
        "[Pool] 10/10 Tier-1 bots connected (0 GUI windows)",
        "[Bridge] TPS=19.94 MSPT=14.2ms Heap=1120/4096MB",
        "[Folia] 4 active threaded regions, 0 barrier stalls",
        "[MCKit] Zero SEVERE traces in bridge error ring"
      ]
    },
    {
      id: "shader-pack",
      label: "Shader + Resource Pack Visual",
      header: "Docker Xvfb Fabric Client + shadersmith",
      badge: "VISUAL OK",
      stages: [
        ["shadersmith GLSL std140 & 26.3 Audit", "PASS"],
        ["packmigrate CustomModelData Check", "PASS"],
        ["Boot Off-Screen Docker Xvfb Client", "PASS"],
        ["Reload Resource Pack (0 Shader Errors)", "PASS"],
        ["Capture Off-Screen Framebuffer PNG", "PASS"],
        ["Encode 10s MP4 Timelapse via ffmpeg", "PASS"]
      ],
      slots: { 10: "STAFF*", 12: "CROWN*", 14: "WING*", 16: "GLYPH" },
      chat: [
        "[ShaderSmith] 0 std140 UBO layout violations",
        "[ClientMod] DISPLAY=:99 off-screen capture ready",
        "[ClientMod] Resource pack reloaded in 420ms (0 errors)",
        "[MCKit] Attached real rendered PNG + session.mp4"
      ]
    }
  ];

  var SUITE_TOOLS = [
    { id: "mcstage", cat: "runtime-testing", lang: "Kotlin", desc: "Real Paper/Folia/Purpur matrix runner with crash-guard MCS001-MCS017, Folia multi-region lag/recovery, RCON fault injection, JUnit & SARIF.", cmd: "java -jar mcstage.jar test mcstage.yml --accept-eula --sarif mcstage.sarif" },
    { id: "shadersmith", cat: "shaders", lang: "Kotlin", desc: "GLSL core & post-effect shader contract validator, std140 UBO layout checker, and 26.3 migrator.", cmd: "java -jar shadersmith.jar check ./pack --target 26.3 --sarif shaders.sarif" },
    { id: "packmigrate", cat: "resource-pack", lang: "Kotlin", desc: "Deterministic 1.20..26.3 CustomModelData & overlay migrator with perceptual asset dedup.", cmd: "java -jar packmigrate.jar migrate ./old ./new --to 26.3" },
    { id: "packmerge", cat: "resource-pack", lang: "Kotlin", desc: "Deterministic resource pack union compiler for 1.21.4+ item models, fonts, sounds, lang, and atlases.", cmd: "java -jar packmerge.jar merge a.zip b.zip -o merged.zip" },
    { id: "glyphsmith", cat: "resource-pack", lang: "Kotlin", desc: "Bitmap font glyph solver, negative-space shift compiler, lockfile generator & pack font auditor.", cmd: "java -jar glyphsmith.jar audit ./pack --json" },
    { id: "pluginscope", cat: "static-audit", lang: "Kotlin", desc: "Static plugin JAR packaging, shading hygiene, Paper API compat & stack conflict auditor + MCP.", cmd: "java -jar pluginscope.jar jar build/libs/Plugin.jar --target 26.3" },
    { id: "serverdoctor", cat: "diagnostics", lang: "Kotlin", desc: "Offline server diagnostics across logs, configs, JVM flags, GC, crash reports, Spark & worlds + MCP.", cmd: "java -jar serverdoctor.jar scan ./server --format json" },
    { id: "foliascan", cat: "static-audit", lang: "Kotlin", desc: "Bytecode taint-flow verifier pinpointing where a plugin JAR breaks on Folia regionized multithreading.", cmd: "java -jar foliascan.jar build/libs/Plugin.jar --format sarif" },
    { id: "rp-engine", cat: "resource-pack", lang: "Java/Kotlin", desc: "Resource pack delivery engine building per-player packs and powering models, emotes & animations.", cmd: "mc_suite_orchestrate tool_id=rp-engine" },
    { id: "texlab", cat: "textures", lang: "TypeScript", desc: "Pixel art Minecraft resource pack texture editor with native AI MCP integration.", cmd: "mc_suite_orchestrate tool_id=texlab" }
  ];

  var CONFIGS = {
    "Claude Code / Codex": "npx minecraftkit install --target both\n\n# Add MCP server (.mcp.json):\n{\n  \"mcpServers\": {\n    \"minecraftkit\": {\n      \"command\": \"npx\",\n      \"args\": [\"-y\", \"minecraftkit\", \"mcp\"]\n    }\n  }\n}",
    "Cursor / Windsurf": "{\n  \"mcpServers\": {\n    \"minecraftkit\": {\n      \"command\": \"npx\",\n      \"args\": [\"-y\", \"minecraftkit\", \"mcp\"]\n    }\n  }\n}",
    "Direct Python (0ms startup)": "{\n  \"mcpServers\": {\n    \"minecraftkit\": {\n      \"command\": \"python3\",\n      \"args\": [\"-B\", \"/path/to/minecraftkit/scripts/mcp_server.py\"]\n    }\n  }\n}",
    "Docker Hybrid Bot Grid": "docker compose -f docker/docker-compose.testgrid.yml up --build\n# Runs 8 Tier-1 protocol bots (336 MB) + 1 off-screen Xvfb visual client!"
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function clear(node) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
  }

  function applyLanguage(lang) {
    var dict = I18N[lang] || I18N.en;
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      if (dict[key]) { node.textContent = dict[key]; }
    });
    document.querySelectorAll(".sc-lang-btn").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-sc-lang") === lang);
    });
  }

  function initPipeline() {
    var rail = document.getElementById("pipeline-steps");
    var detail = document.getElementById("pipeline-detail");
    if (!rail || !detail) { return; }

    function select(index) {
      var item = PIPELINE[index];
      rail.querySelectorAll(".sc-pipe-btn").forEach(function (btn, idx) {
        btn.classList.toggle("is-active", idx === index);
        btn.setAttribute("aria-selected", String(idx === index));
      });
      clear(detail);
      detail.append(
        el("span", "sc-tag", item.step + " · " + item.tool),
        el("h3", "", item.name),
        el("p", "sc-muted", item.desc),
        el("pre", "sc-code-block", item.sample)
      );
    }

    PIPELINE.forEach(function (item, idx) {
      var btn = el("button", "sc-pipe-btn");
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.append(el("small", "", item.step), el("strong", "", item.name));
      btn.addEventListener("click", function () { select(idx); });
      rail.append(btn);
    });
    select(0);
  }

  function initRamCalculator() {
    var botsInput = document.getElementById("calc-bots");
    var ramInput = document.getElementById("calc-ram");
    var visualInput = document.getElementById("calc-visual");
    var botsVal = document.getElementById("calc-bots-val");
    var ramVal = document.getElementById("calc-ram-val");
    var bars = document.getElementById("calc-bars");
    var savings = document.getElementById("calc-savings");
    var strategyBox = document.getElementById("calc-strategy-box");
    if (!botsInput || !bars) { return; }

    function update() {
      var n = Number(botsInput.value);
      var hostGb = Number(ramInput.value);
      var visual = Boolean(visualInput.checked);
      botsVal.textContent = n + (n === 1 ? " bot" : " bots");
      ramVal.textContent = hostGb + " GB";

      var tier1Mb = n * 42;
      var hybridMb = visual ? (1400 + Math.max(0, n - 1) * 42) : tier1Mb;
      var allVisualMb = n * 1400;
      var desktopMb = n * 2600;
      var maxMb = Math.max(desktopMb, 1);

      var rows = [
        { label: "Tier-1 Headless Protocol (" + n + "x 42 MB)", mb: tier1Mb, cls: "sc-bar-emerald" },
        { label: "Recommended Hybrid (1 Xvfb Visual + " + Math.max(0, n - 1) + " Protocol)", mb: hybridMb, cls: "sc-bar-cyan" },
        { label: "All Docker Xvfb Visual (" + n + "x 1.4 GB)", mb: allVisualMb, cls: "sc-bar-amber" },
        { label: "Full Desktop Minecraft Tabs (" + n + "x 2.6 GB · Focus Lock)", mb: desktopMb, cls: "sc-bar-red" }
      ];

      clear(bars);
      rows.forEach(function (row) {
        var wrap = el("div");
        var lbl = el("div", "sc-bar-label");
        lbl.append(el("span", "", row.label), el("strong", "", (row.mb / 1024).toFixed(2) + " GB"));
        var track = el("div", "sc-bar-track");
        var fill = el("div", "sc-bar-fill " + row.cls);
        fill.style.width = Math.max(2, Math.round((row.mb / maxMb) * 100)) + "%";
        track.append(fill);
        wrap.append(lbl, track);
        bars.append(wrap);
      });

      var savedPct = ((1 - hybridMb / desktopMb) * 100).toFixed(1);
      savings.textContent = "Recommended strategy saves " + savedPct + "% RAM (" + ((desktopMb - hybridMb) / 1024).toFixed(1) + " GB freed) with ZERO desktop screen hijacking.";
      var safeBudgetGb = (hostGb * 0.65).toFixed(1);
      var fitMsg = (hybridMb / 1024) <= (hostGb * 0.65)
        ? "Fits safely inside your 65% host RAM budget (" + safeBudgetGb + " GB)."
        : "Exceeds local 65% budget (" + safeBudgetGb + " GB) — offload Tier-2 visual container to Cloud Docker Grid.";
      strategyBox.textContent = "Active Strategy: " + (visual ? "Hybrid 1 Visual Docker/Xvfb + " + Math.max(0, n - 1) + " Headless Protocol" : "Pure Tier-1 Headless Protocol Pool") + ". " + fitMsg;
    }

    botsInput.addEventListener("input", update);
    ramInput.addEventListener("input", update);
    visualInput.addEventListener("change", update);
    update();
  }

  function initSimulator() {
    var controls = document.getElementById("sim-presets");
    var stageList = document.getElementById("sim-stages");
    var hudTitle = document.getElementById("sim-hud-title");
    var hudBadge = document.getElementById("sim-hud-badge");
    var guiGrid = document.getElementById("sim-gui-grid");
    var chatBox = document.getElementById("sim-chat-box");
    if (!controls || !stageList) { return; }

    function renderPreset(idx) {
      var p = PRESETS[idx];
      controls.querySelectorAll(".sc-chip").forEach(function (b, i) {
        b.classList.toggle("is-active", i === idx);
      });
      hudTitle.textContent = p.header;
      hudBadge.textContent = p.badge;

      clear(stageList);
      p.stages.forEach(function (pair) {
        var li = el("li", "sc-stage-item");
        li.append(el("span", "", pair[0]), el("span", "sc-badge-ok", pair[1]));
        stageList.append(li);
      });

      clear(guiGrid);
      for (var s = 0; s < 27; s++) {
        var label = p.slots[s] || String(s);
        var cell = el("div", p.slots[s] ? "sc-slot is-filled" : "sc-slot", label);
        guiGrid.append(cell);
      }

      clear(chatBox);
      p.chat.forEach(function (line) {
        chatBox.append(el("div", "", line));
      });
    }

    PRESETS.forEach(function (preset, idx) {
      var btn = el("button", "sc-chip", preset.label);
      btn.type = "button";
      btn.addEventListener("click", function () { renderPreset(idx); });
      controls.append(btn);
    });
    renderPreset(0);
  }

  function initSuite() {
    var filters = document.getElementById("suite-filters");
    var grid = document.getElementById("suite-grid");
    if (!filters || !grid) { return; }
    var cats = ["all", "runtime-testing", "static-audit", "resource-pack", "shaders", "diagnostics", "textures"];

    function render(cat) {
      filters.querySelectorAll(".sc-chip").forEach(function (btn) {
        btn.classList.toggle("is-active", btn.getAttribute("data-cat") === cat);
      });
      clear(grid);
      SUITE_TOOLS.filter(function (t) { return cat === "all" || t.cat === cat; }).forEach(function (tool) {
        var card = el("article", "sc-suite-card");
        card.append(
          el("span", "sc-tag", tool.cat.toUpperCase() + " · " + tool.lang),
          el("h3", "", "SalyyS1/" + tool.id),
          el("p", "", tool.desc),
          el("code", "", tool.cmd)
        );
        grid.append(card);
      });
    }

    cats.forEach(function (cat) {
      var btn = el("button", "sc-chip", cat);
      btn.type = "button";
      btn.setAttribute("data-cat", cat);
      btn.addEventListener("click", function () { render(cat); });
      filters.append(btn);
    });
    render("all");
  }

  function initConfigBuilder() {
    var tabs = document.getElementById("cfg-tabs");
    var code = document.getElementById("cfg-code");
    var copyBtn = document.getElementById("cfg-copy");
    var status = document.getElementById("cfg-status");
    if (!tabs || !code) { return; }

    var keys = Object.keys(CONFIGS);
    var active = keys[0];

    function select(name) {
      active = name;
      tabs.querySelectorAll(".sc-chip").forEach(function (b) {
        b.classList.toggle("is-active", b.textContent === name);
      });
      code.textContent = CONFIGS[name];
      status.textContent = "";
    }

    keys.forEach(function (name) {
      var btn = el("button", "sc-chip", name);
      btn.type = "button";
      btn.addEventListener("click", function () { select(name); });
      tabs.append(btn);
    });

    copyBtn.addEventListener("click", function () {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(CONFIGS[active]).then(function () {
          status.textContent = "Copied to clipboard!";
        }).catch(function () {
          status.textContent = "Select and copy the snippet above.";
        });
      } else {
        status.textContent = "Select and copy the snippet above.";
      }
    });

    select(active);
  }

  function init() {
    document.querySelectorAll(".sc-lang-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyLanguage(btn.getAttribute("data-sc-lang") || "en");
      });
    });
    initPipeline();
    initRamCalculator();
    initSimulator();
    initFreeformConsole();
    initVisualDiffLab();
    initSuite();
    initConfigBuilder();
  }

  function initVisualDiffLab() {
    var ctrl = document.getElementById("vdiff-controls");
    var cBase = document.getElementById("vdiff-base");
    var cCand = document.getElementById("vdiff-cand");
    var cOut = document.getElementById("vdiff-out");
    var stats = document.getElementById("vdiff-stats");
    if (!ctrl || !cBase || !cCand || !cOut) { return; }

    var MODES = [
      { id: "slot-shift", label: "Slot #13 Shifted Regression" },
      { id: "tps-drop", label: "TPS Drop Alert Banner" },
      { id: "clean", label: "Zero Regression (Identical)" }
    ];

    function drawGui(ctx, variant) {
      ctx.fillStyle = "#0b131e";
      ctx.fillRect(0, 0, 260, 150);
      ctx.fillStyle = variant === "tps-drop" ? "#5a1d24" : "#152538";
      ctx.fillRect(8, 8, 244, 22);
      ctx.fillStyle = variant === "tps-drop" ? "#ff7b89" : "#48e8b2";
      ctx.font = "bold 11px monospace";
      ctx.fillText(variant === "tps-drop" ? "RPG SHOP  |  TPS 14.2 (LAG)" : "RPG SHOP  |  TPS 20.0 (OK)", 16, 23);

      for (var r = 0; r < 3; r++) {
        for (var c = 0; c < 7; c++) {
          var sx = 14 + c * 34;
          var sy = 38 + r * 34;
          ctx.fillStyle = "#121e2c";
          ctx.fillRect(sx, sy, 28, 28);
          ctx.strokeStyle = "#2b4257";
          ctx.strokeRect(sx + 0.5, sy + 0.5, 27, 27);
        }
      }
      // Highlighted Mythic Blade slot
      var bladeCol = variant === "slot-shift" ? 4 : 3;
      var bx = 14 + bladeCol * 34;
      var by = 38 + 34;
      ctx.fillStyle = "#2d5a48";
      ctx.fillRect(bx + 2, by + 2, 24, 24);
      ctx.fillStyle = "#ffe082";
      ctx.fillRect(bx + 9, by + 6, 10, 14);
    }

    function render(modeId) {
      ctrl.querySelectorAll(".sc-chip").forEach(function (b) {
        b.classList.toggle("is-active", b.getAttribute("data-mode") === modeId);
      });
      var ctxB = cBase.getContext("2d");
      var ctxC = cCand.getContext("2d");
      var ctxO = cOut.getContext("2d");
      drawGui(ctxB, "base");
      drawGui(ctxC, modeId === "clean" ? "base" : modeId);

      var imgB = ctxB.getImageData(0, 0, 260, 150);
      var imgC = ctxC.getImageData(0, 0, 260, 150);
      var imgO = ctxO.createImageData(260, 150);
      var changed = 0;
      var minX = 260, minY = 150, maxX = -1, maxY = -1;
      for (var y = 0; y < 150; y++) {
        for (var x = 0; x < 260; x++) {
          var i = (y * 260 + x) * 4;
          var dr = Math.abs(imgB.data[i] - imgC.data[i]);
          var dg = Math.abs(imgB.data[i + 1] - imgC.data[i + 1]);
          var db = Math.abs(imgB.data[i + 2] - imgC.data[i + 2]);
          if (dr > 6 || dg > 6 || db > 6) {
            changed++;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
            imgO.data[i] = 248;
            imgO.data[i + 1] = 81;
            imgO.data[i + 2] = 73;
            imgO.data[i + 3] = 255;
          } else {
            imgO.data[i] = Math.round(imgC.data[i] * 0.45);
            imgO.data[i + 1] = Math.round(imgC.data[i + 1] * 0.45);
            imgO.data[i + 2] = Math.round(imgC.data[i + 2] * 0.45);
            imgO.data[i + 3] = 255;
          }
        }
      }
      ctxO.putImageData(imgO, 0, 0);
      if (maxX >= minX) {
        ctxO.strokeStyle = "#fbbf24";
        ctxO.lineWidth = 2;
        ctxO.strokeRect(minX - 2, minY - 2, (maxX - minX) + 4, (maxY - minY) + 4);
      }
      var pct = ((changed / (260 * 150)) * 100).toFixed(2);
      if (stats) {
        stats.textContent = changed === 0
          ? "identical: true | changed_pixels: 0 (0.00%)"
          : "identical: false | changed_pixels: " + changed + " (" + pct + "%) | bbox: [" + minX + "," + minY + "," + maxX + "," + maxY + "]";
      }
    }

    MODES.forEach(function (m) {
      var btn = el("button", "sc-chip", m.label);
      btn.type = "button";
      btn.setAttribute("data-mode", m.id);
      btn.addEventListener("click", function () { render(m.id); });
      ctrl.append(btn);
    });
    render("slot-shift");
  }

  function initFreeformConsole() {
    var input = document.getElementById("sim-cmd-input");
    var btn = document.getElementById("sim-cmd-send");
    var chat = document.getElementById("sim-chat-box");
    var badge = document.getElementById("sim-hud-badge");
    if (!input || !btn || !chat) { return; }

    function runCmd() {
      var raw = String(input.value || "").trim();
      if (!raw) { return; }
      var redacted = raw.replace(/^(\/(?:login|l|register|reg|changepassword|cpw)\s+)(.+)$/i, "$1[REDACTED_PASSWORD]");
      chat.append(el("div", "sc-chat-line", "[Bot] " + redacted));
      if (/^\/(?:login|l|register|reg)\b/i.test(raw)) {
        chat.append(el("div", "sc-chat-line", "[AuthMe] Authenticated! Password scrubbed from transcript."));
        if (badge) { badge.textContent = "AUTHENTICATED"; }
      } else if (/^\/(?:shop|ia|nexo|menu)\b/i.test(raw)) {
        chat.append(el("div", "sc-chat-line", "[MCKit] GUI opened -> rendered 9x4 PNG diff frame attached to chat."));
      } else {
        chat.append(el("div", "sc-chat-line", "[MCKit] Action executed off-screen (42 MB RAM, 0 GUI windows)."));
      }
      input.value = "";
      chat.scrollTop = chat.scrollHeight;
    }

    btn.addEventListener("click", runCmd);
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); runCmd(); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
