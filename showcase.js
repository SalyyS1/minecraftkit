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
    },
    {
      id: "towny-lands",
      label: "Towny / Lands Claim",
      header: "MCKitClaimBot @ survival.salyvn.net:25565 (42 MB RAM)",
      badge: "7/7 PASSED",
      stages: [
        ["Join Survival Paper 1.21.4", "PASS"],
        ["Auto-Auth /login [REDACTED]", "PASS"],
        ["Run /lands claim & Assert Feedback", "PASS"],
        ["Open /lands menu Container GUI", "PASS"],
        ["Verify Roles, Flags & Trust Slots", "PASS"],
        ["Render Off-Screen Claim PNG", "PASS"]
      ],
      slots: { 11: "CLAIM", 13: "ROLES", 15: "FLAGS", 22: "TRUST" },
      chat: [
        "[Lands] Chunk (12, -4) claimed for Town SalyVn",
        "[Lands] Opened Land Management Menu (4 active icons)",
        "[MCKit] Zero permission leaks; PNG snapshot attached"
      ]
    },
    {
      id: "skyblock-coop",
      label: "Skyblock Island Coop",
      header: "MCKitSkyBot @ skyblock.salyvn.net:25565 (42 MB RAM)",
      badge: "TPS 20.0",
      stages: [
        ["Join BentoBox / SuperiorSkyblock2", "PASS"],
        ["Auto-Auth /login [REDACTED]", "PASS"],
        ["Run /is go & Paste Island Schematic", "PASS"],
        ["Verify Scoreboard Island Level", "PASS"],
        ["Assert TPS >= 19.0 After Paste", "PASS"],
        ["Attach Bridge 60s TPS Sparkline PNG", "PASS"]
      ],
      slots: { 10: "ISLAND", 12: "COOP", 14: "CHALLENGES", 16: "WARP" },
      chat: [
        "[Skyblock] Teleported to Island (Level 124)",
        "[Bridge] TPS=20.00 MSPT=11.4ms TopEntity=ITEM(12)",
        "[MCKit] Attached 640x240 inline TPS sparkline PNG"
      ]
    },
    {
      id: "modelengine-boss",
      label: "ModelEngine 3D Boss",
      header: "Hybrid Tier-2 Xvfb + Bridge Entities (1.4 GB Total)",
      badge: "BOSS OK",
      stages: [
        ["Accept ModelEngine Custom Pack", "PASS"],
        ["Warp /warp boss_arena", "PASS"],
        ["Verify Custom Entity Hitbox & Count", "PASS"],
        ["Bridge /api/v1/entities Lag Check", "PASS"],
        ["Capture Off-Screen Xvfb PNG + GIF", "PASS"]
      ],
      slots: { 0: "EXCALIBUR*", 1: "ELIXIR", 4: "BOSS_KEY*", 8: "COMPANION" },
      chat: [
        "[ModelEngine] Loaded 18 blueprint animations (0 errors)",
        "[Bridge] Entities=42 TPS=19.95 MSPT=15.8ms",
        "[MCKit] Attached keyframe.png + session.gif to chat"
      ]
    },
    {
      id: "itemsadder-pack",
      label: "ItemsAdder / Nexo Pack",
      header: "Hybrid Tier-2 Xvfb Pack QA (1.4 GB Total)",
      badge: "PACK OK",
      stages: [
        ["Join Custom-Pack Server", "PASS"],
        ["Auto-Auth /login [REDACTED]", "PASS"],
        ["Accept Forced Resource Pack", "PASS"],
        ["Open /ia Custom Item Menu", "PASS"],
        ["Verify Glyph HUD Title & PNG", "PASS"]
      ],
      slots: { 10: "RUBY_SWORD*", 12: "CUSTOM_HAT", 14: "GLYPH_UI", 16: "EMOTE_PACK" },
      chat: [
        "[ItemsAdder] Resource pack loaded (SHA-1 verified)",
        "[MCKit] assert_gui matched /itemsadder|custom/ (27 slots)",
        "[MCKit] Attached off-screen Xvfb PNG + badge_json"
      ]
    },
    {
      id: "dungeon-boss",
      label: "Dungeon Boss Proximity",
      header: "MCKitBossBot @ dungeons.salyvn.net:25565 (42 MB RAM)",
      badge: "BOSS NEAR",
      stages: [
        ["Join MythicDungeons Lobby", "PASS"],
        ["Auto-Auth /login [REDACTED]", "PASS"],
        ["Enter /md play crypt", "PASS"],
        ["assert_title: BOSS SPAWNED", "PASS"],
        ["assert_entity_nearby <= 24m", "PASS"],
        ["Bridge /api/v1/chunks PNG", "PASS"]
      ],
      slots: { 0: "CRYPT_BLADE*", 1: "HEAL_POT", 4: "DUNGEON_KEY", 8: "MAP" },
      chat: [
        "[MythicDungeons] Instance crypt_04 started (1/1)",
        "[MCKit] Found entity Crimson_Lich at 11.4m (<= 24m)",
        "[Bridge] Chunks=184 Density=1.2/c TPS=20.00"
      ]
    }
  ];

  var SUITE_TOOLS = [
    { id: "mcstage", cat: "runtime-testing", lang: "Kotlin", desc: "Real Paper/Folia/Purpur matrix runner & 15-tool stdio MCP server with crash-guard MCS001-MCS023, budget/probe/check-world/inspect-jar/preflight CLI, 4 init presets, HTML diffs, JUnit & SARIF.", cmd: "java -jar mcstage.jar budget mcstage.yml --host-ram-gb 7 --max-shards 4" },
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
    initYamlBuilder();
    initOpsLab();
    initSuite();
    initConfigBuilder();
    initToolExplorer();
    initVpsPlanner();
    initTpsSparklineLab();
  }

  function initTpsSparklineLab() {
    var tabs = document.getElementById("tps-lab-tabs");
    var canvas = document.getElementById("tps-canvas");
    var stats = document.getElementById("tps-stats");
    if (!tabs || !canvas) { return; }

    var PROFILES = [
      {
        id: "healthy-folia",
        label: "Healthy Folia (20.0 TPS)",
        tps: [20.0, 20.0, 19.98, 20.0, 19.99, 20.0, 19.97, 20.0, 20.0, 19.98, 20.0, 20.0],
        mspt: [11.2, 11.8, 12.1, 11.5, 12.4, 11.9, 12.6, 11.4, 11.7, 12.0, 11.3, 11.6],
        topEntity: "ITEM (18), VILLAGER (14), ARMOR_STAND (9)",
        verdict: "HEALTHY — Bridge /api/v1/tps-history + /api/v1/entities PASS"
      },
      {
        id: "chunk-spike",
        label: "Chunk Gen Spike (17.4 TPS)",
        tps: [20.0, 19.9, 19.6, 18.8, 17.4, 17.9, 18.7, 19.3, 19.8, 19.9, 20.0, 20.0],
        mspt: [14.0, 16.5, 22.1, 34.8, 48.2, 41.0, 29.4, 21.2, 16.9, 15.1, 14.3, 13.8],
        topEntity: "FALLING_BLOCK (112), ITEM (84), BOAT (16)",
        verdict: "WARN — Pre-generate world chunks (Chunky) before launch"
      },
      {
        id: "mob-farm-lag",
        label: "Entity Mob-Farm Lag (14.2 TPS)",
        tps: [19.8, 19.1, 18.2, 16.9, 15.6, 14.8, 14.2, 14.5, 14.3, 14.7, 15.0, 14.9],
        mspt: [19.2, 27.4, 38.9, 52.1, 61.8, 68.4, 73.2, 70.1, 71.5, 66.8, 64.2, 65.0],
        topEntity: "ZOMBIFIED_PIGLIN (428), ITEM (319), XP_ORB (204)",
        verdict: "ALERT — Triggered /api/v1/entities top-10 lag diagnostics!"
      }
    ];

    function draw(id) {
      var p = PROFILES.find(function (x) { return x.id === id; }) || PROFILES[0];
      tabs.querySelectorAll(".sc-chip").forEach(function (b) {
        b.classList.toggle("is-active", b.getAttribute("data-tps") === p.id);
      });
      var ctx = canvas.getContext("2d");
      var w = canvas.width;
      var h = canvas.height;
      ctx.fillStyle = "#081018";
      ctx.fillRect(0, 0, w, h);

      ctx.strokeStyle = "#1b2c3d";
      ctx.lineWidth = 1;
      for (var gy = 36; gy <= h - 30; gy += 36) {
        ctx.beginPath();
        ctx.moveTo(42, gy);
        ctx.lineTo(w - 16, gy);
        ctx.stroke();
      }
      ctx.fillStyle = "#8aa5be";
      ctx.font = "11px monospace";
      ctx.fillText("20 TPS", 4, 40);
      ctx.fillText("15 TPS", 4, 112);
      ctx.fillText("10 TPS", 4, 184);

      ctx.fillStyle = "#48e8b2";
      ctx.font = "bold 12px monospace";
      ctx.fillText("mckit-bridge-plugin :: /api/v1/tps-history (" + p.label + ")", 44, 20);

      var minTps = Math.min.apply(null, p.tps);
      var lineColor = minTps >= 19.0 ? "#48e8b2" : (minTps >= 16.5 ? "#fbbf24" : "#f85149");
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = 3;
      ctx.beginPath();
      p.tps.forEach(function (val, idx) {
        var x = 48 + idx * ((w - 72) / (p.tps.length - 1));
        var norm = Math.max(0, Math.min(1, (val - 10) / 10));
        var y = (h - 32) - norm * (h - 72);
        if (idx === 0) { ctx.moveTo(x, y); } else { ctx.lineTo(x, y); }
      });
      ctx.stroke();

      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      p.mspt.forEach(function (val, idx) {
        var x = 48 + idx * ((w - 72) / (p.mspt.length - 1));
        var norm = Math.max(0, Math.min(1, val / 80));
        var y = (h - 32) - norm * (h - 72);
        if (idx === 0) { ctx.moveTo(x, y); } else { ctx.lineTo(x, y); }
      });
      ctx.stroke();

      ctx.fillStyle = lineColor;
      ctx.fillText("TPS line", w - 150, 20);
      ctx.fillStyle = "#38bdf8";
      ctx.fillText("MSPT line", w - 80, 20);

      if (stats) {
        var avgMspt = (p.mspt.reduce(function (a, b) { return a + b; }, 0) / p.mspt.length).toFixed(1);
        stats.textContent = p.verdict + " | Min TPS: " + minTps.toFixed(2) + " | Avg MSPT: " + avgMspt + "ms | Top Entities: " + p.topEntity;
      }
    }

    PROFILES.forEach(function (p) {
      var btn = el("button", "sc-chip", p.label);
      btn.type = "button";
      btn.setAttribute("data-tps", p.id);
      btn.addEventListener("click", function () { draw(p.id); });
      tabs.append(btn);
    });
    draw("healthy-folia");
  }

  function initVpsPlanner() {
    var ramIn = document.getElementById("vps-ram");
    var gcIn = document.getElementById("vps-gc");
    var topoIn = document.getElementById("vps-topo");
    var out = document.getElementById("vps-out");
    var copyBtn = document.getElementById("vps-copy");
    var status = document.getElementById("vps-status");
    if (!ramIn || !out) { return; }

    function render() {
      var ram = Math.max(4, Math.min(64, Number(ramIn.value) || 16));
      var osReserve = ram <= 8 ? 2 : Math.max(3, Math.round(ram * 0.2));
      var heap = Math.max(2, ram - osReserve);
      var gc = gcIn ? gcIn.value : "zgc";
      var topo = topoIn ? topoIn.value : "velocity";
      var gcFlags = gc === "zgc"
        ? "-XX:+UseZGC -XX:+ZGenerational -XX:+AlwaysPreTouch"
        : "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=120 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch";
      var lines = [
        "# Safe Heap Budget: " + heap + "G JVM / " + ram + "G VPS (" + osReserve + "G OS + Netty + Bot Pool reserve)",
        "java -Xms" + heap + "G -Xmx" + heap + "G " + gcFlags + " -jar server.jar --nogui",
        "",
        "# Zero-Exposure UFW Firewall Rules (Loopback Bridge 25590 & RCON 25575 stay private)",
        "sudo ufw default deny incoming",
        "sudo ufw allow 22/tcp"
      ];
      if (topo === "velocity") {
        lines.push("sudo ufw allow 25565/tcp   # Velocity Java proxy");
        lines.push("sudo ufw allow 19132/udp   # Geyser Bedrock UDP");
        lines.push("# Backend Paper/Folia nodes: server-ip=127.0.0.1, online-mode=false, modern forwarding secret!");
      } else {
        lines.push("sudo ufw allow 25565/tcp   # Standalone Java server (online-mode=true)");
      }
      lines.push("sudo ufw deny 25575/tcp    # Never expose plaintext Source RCON publicly");
      lines.push("sudo ufw deny 25590/tcp    # Keep mckit-bridge-plugin strictly 127.0.0.1");
      out.textContent = lines.join("\n");
      if (status) { status.textContent = ""; }
    }

    ramIn.addEventListener("input", render);
    if (gcIn) { gcIn.addEventListener("change", render); }
    if (topoIn) { topoIn.addEventListener("change", render); }
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(out.textContent).then(function () {
            if (status) { status.textContent = "Copied VPS plan!"; }
          }).catch(function () {});
        }
      });
    }
    render();
  }

  function initToolExplorer() {
    var searchIn = document.getElementById("tool-search");
    var catRow = document.getElementById("tool-cats");
    var listEl = document.getElementById("tool-list");
    var countEl = document.getElementById("tool-count");
    if (!searchIn || !catRow || !listEl) { return; }

    var FEATURED_TOOLS = [
      { id: "mc_bot_fingerprint_server", cat: "bot", desc: "1-call ~15MB Java SLP + Bedrock UDP + Bridge health + protocol matrix + ready-to-run bot config." },
      { id: "mc_bot_run_stages", cat: "bot", desc: "Headless ~42MB Mineflayer bot: auto-join, AuthMe/nLogin auto-auth, stage YAML & inline PNG proof." },
      { id: "mc_bot_play_command_probe", cat: "bot", desc: "Zero-dependency ~18MB pure-Python wire bot traversing Login -> Config -> Play -> ChatCommand." },
      { id: "mc_bot_probe_protocol_matrix", cat: "bot", desc: "1.20.4..26.3 native vs ViaVersion / ViaBackwards / Geyser protocol compatibility matrix." },
      { id: "mc_bot_record_stage_gif", cat: "bot", desc: "Stitches off-screen bot stages into an MCP-attached PNG storyboard & ffmpeg animated GIF." },
      { id: "mc_bot_visual_diff", cat: "bot", desc: "Pixel-exact GUI/HUD regression diff with red bounding-box overlay attached directly to chat." },
      { id: "mc_bot_stress_benchmark", cat: "bot", desc: "Multi-bot concurrent swarm benchmark with anti-OOM RAM cap & p95 join latency metrics." },
      { id: "mc_bot_generate_fabric_capture_script", cat: "bot", desc: "Generates memory-capped Xvfb + Fabric mckit-client-mod off-screen 3D screenshot scripts." },
      { id: "mc_bot_compare_stage_runs", cat: "bot", desc: "Diffs baseline vs current bot QA runs to catch latency & step regressions in CI." },
      { id: "mc_hosting_connect_plan", cat: "ops", desc: "Zero-screen-lock Pterodactyl, Pelican, Crafty & PufferPanel plan with RFC 6238 TOTP 2FA." },
      { id: "mc_hosting_server_action", cat: "ops", desc: "Headless start/stop/restart/console/status API dispatch with strict token redaction." },
      { id: "mc_sftp_operations", cat: "ops", desc: "Atomic SFTP plugin JAR deploy, safe config patching & automatic .mckit.bak backups." },
      { id: "mc_ops_profile_vault", cat: "ops", desc: "chmod 0600 local credential vault for hosting/SFTP/RCON/bridge profiles (masked outputs)." },
      { id: "mc_ops_vps_ssh_preflight", cat: "ops", desc: "Anti-OOM JVM G1GC/ZGC heap calculator & UFW firewall rules for Minecraft VPS hosts." },
      { id: "mc_ops_generate_docker_stack", cat: "ops", desc: "Full-stack Paper/Folia/Velocity + headless protocol & Xvfb visual bot docker-compose generator." },
      { id: "mc_audit_server_exploits", cat: "audit", desc: "Static security audit for chunk bans, command injection, packet flood & dupe exploits (EXPLOIT-001..005)." },
      { id: "mc_world_audit_integrity", cat: "audit", desc: "Zero-JVM Anvil .mca 4096-byte sector, GZIP level.dat & playerdata corruption scanner (WORLD-001..005)." },
      { id: "mc_audit_proxy_topology", cat: "audit", desc: "Velocity, Paper, BungeeCord & Geyser-Floodgate forwarding secret & IP spoofing auditor." },
      { id: "mc_audit_permissions_rbac", cat: "audit", desc: "LuckPerms, Vault & plugin.yml wildcard/OP escalation privilege auditor (PERM-001..005)." },
      { id: "mc_audit_database_pool", cat: "audit", desc: "HikariCP, MySQL & SQLite connection pool leak & main-thread blocking auditor (DB-001..005)." },
      { id: "mc_audit_shader_pack", cat: "audit", desc: "GLSL 1.21+ core shader, std140 UBO & legacy syntax validator (SHD-001..005)." },
      { id: "mc_ops_audit_spark_profile", cat: "audit", desc: "Spark profiler JSON/log analyzer pinpointing entity, chunk, GC & blocking-IO lag spikes." },
      { id: "mc_qa_run_full_lifecycle", cat: "suite", desc: "Single-call E2E pipeline: deploy -> host restart -> bot QA stages -> bridge telemetry -> HTML proof." },
      { id: "mc_suite_full_ecosystem_doctor", cat: "suite", desc: "Unified health check across Python, Node, Java 21, Docker, ffmpeg, companion bridges & 10 repos." },
      { id: "mc_search_rpg_api", cat: "suite", desc: "Offline bytecode-verified search across 41,887 members in 10 RPG plugins (MMOItems, ModelEngine...)." }
    ];

    var activeCat = "all";
    var cats = ["all", "bot", "ops", "audit", "suite"];

    function render() {
      var q = String(searchIn.value || "").trim().toLowerCase();
      catRow.querySelectorAll(".sc-chip").forEach(function (b) {
        b.classList.toggle("is-active", b.getAttribute("data-tcat") === activeCat);
      });
      var matches = FEATURED_TOOLS.filter(function (t) {
        var okCat = activeCat === "all" || t.cat === activeCat;
        var okQ = !q || t.id.toLowerCase().indexOf(q) >= 0 || t.desc.toLowerCase().indexOf(q) >= 0 || t.cat.indexOf(q) >= 0;
        return okCat && okQ;
      });
      if (countEl) {
        countEl.textContent = "Showing " + matches.length + " featured tools out of 78 live stdio MCP tools (filter by keyword or category).";
      }
      clear(listEl);
      matches.forEach(function (tool) {
        var card = el("article", "sc-suite-card");
        var copyBtn = el("button", "sc-chip", "Copy MCP Call");
        copyBtn.type = "button";
        copyBtn.addEventListener("click", function () {
          var snippet = '{"tool":"' + tool.id + '","arguments":{}}';
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(snippet).catch(function () {});
          }
          copyBtn.textContent = "Copied!";
          setTimeout(function () { copyBtn.textContent = "Copy MCP Call"; }, 1200);
        });
        card.append(
          el("span", "sc-tag", tool.cat.toUpperCase()),
          el("h3", "", tool.id),
          el("p", "", tool.desc),
          copyBtn
        );
        listEl.append(card);
      });
    }

    cats.forEach(function (c) {
      var btn = el("button", "sc-chip", c);
      btn.type = "button";
      btn.setAttribute("data-tcat", c);
      btn.addEventListener("click", function () { activeCat = c; render(); });
      catRow.append(btn);
    });
    searchIn.addEventListener("input", render);
    render();
  }

  function initYamlBuilder() {
    var hostIn = document.getElementById("yb-host");
    var portIn = document.getElementById("yb-port");
    var verIn = document.getElementById("yb-ver");
    var authIn = document.getElementById("yb-auth");
    var guiIn = document.getElementById("yb-gui");
    var snapIn = document.getElementById("yb-snap");
    var out = document.getElementById("yb-out");
    var copyBtn = document.getElementById("yb-copy");
    var valBtn = document.getElementById("yb-validate");
    var auditBox = document.getElementById("yb-audit-box");
    var status = document.getElementById("yb-status");
    if (!hostIn || !out) { return; }

    function runStagePreFlight(yamlStr) {
      var issues = [];
      if (/password:\s*["']?(?!env:|\$\{|\[REDACTED)/i.test(yamlStr)) {
        issues.push("STAGE-SEC-001: Hardcoded plaintext password detected.");
      }
      if (/\/(login|register|reg)\s+(?!env:|\$\{|\[REDACTED)\S+/i.test(yamlStr)) {
        issues.push("STAGE-SEC-001: Plaintext auth command in stages.");
      }
      if (/tier:\s*["']?desktop/i.test(yamlStr)) {
        issues.push("STAGE-OOM-001: Desktop tier risks OOM & focus lock.");
      }
      var stageCount = (yamlStr.match(/^\s*-\s+name:/gm) || []).length;
      if (stageCount === 0) {
        issues.push("STAGE-REQ-001: Zero stages defined.");
      }
      return {
        ok: issues.length === 0,
        grade: issues.length === 0 ? "A" : "F",
        stageCount: stageCount,
        issues: issues
      };
    }

    function render() {
      var host = String(hostIn.value || "127.0.0.1").replace(/[\r\n"']/g, "").trim() || "127.0.0.1";
      var port = Math.max(1, Math.min(65535, Number(portIn.value) || 25565));
      var ver = String(verIn.value || "1.21.4");
      var lines = [
        'name: "MinecraftKit Autonomous Bot QA"',
        "target:",
        '  host: "' + host + '"',
        "  port: " + port,
        '  version: "' + ver + '"',
        '  tier: "tier1-protocol"',
        '  password: "env:MCKIT_BOT_PASS"',
        "  screen_lock_free: true",
        "stages:",
        '  - name: "Join & SLP Check"',
        '    action: "join"',
        "    max_latency_ms: 400"
      ];
      if (authIn && authIn.checked) {
        lines.push('  - name: "Auto-Auth (AuthMe/nLogin)"');
        lines.push('    action: "auto_auth"');
        lines.push("    redact_secrets: true");
      }
      if (guiIn && guiIn.checked) {
        lines.push('  - name: "Open RPG Shop GUI"');
        lines.push('    action: "command"');
        lines.push('    command: "/shop"');
        lines.push('  - name: "Verify GUI Slot & Anti-Dupe"');
        lines.push('    action: "click_gui"');
        lines.push("    slot: 13");
      }
      if (snapIn && snapIn.checked) {
        lines.push('  - name: "Capture Off-Screen PNG Proof"');
        lines.push('    action: "snapshot"');
        lines.push("    attach_to_chat: true");
      }
      out.textContent = lines.join("\n") + "\n";
    }

    [hostIn, portIn, verIn, authIn, guiIn, snapIn].forEach(function (node) {
      if (node) {
        node.addEventListener("input", render);
        node.addEventListener("change", render);
      }
    });
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(out.textContent).then(function () {
            if (status) { status.textContent = "Copied .mckit-stages.yml!"; }
          });
        } else if (status) {
          status.textContent = "Select & copy the YAML block above.";
        }
      });
    }
    if (valBtn && auditBox) {
      valBtn.addEventListener("click", function () {
        var res = runStagePreFlight(out.textContent || "");
        auditBox.style.display = "block";
        auditBox.textContent = res.ok
          ? "Pre-Flight PASS · Grade " + res.grade + " · " + res.stageCount + " stages verified · Zero plaintext secrets · Anti-OOM Tier-1 (42 MB/bot) · Screen-Lock Free."
          : "Pre-Flight FAIL · Grade " + res.grade + " · " + res.issues.join(" | ");
      });
    }
    render();
  }

  function initOpsLab() {
    var tabs = document.getElementById("ops-lab-tabs");
    var out = document.getElementById("ops-lab-out");
    if (!tabs || !out) { return; }
    var SAMPLES = [
      {
        id: "wire-login",
        label: "Wire Login Probe (~18 MB)",
        body: JSON.stringify({
          tool: "mc_bot_login_handshake_probe",
          host: "127.0.0.1:25565",
          ram_mb: 18,
          screen_lock: false,
          compression_threshold: 256,
          state_reached: "CONFIGURATION",
          login_success: { username: "MCKitProtoBot", uuid: "00000000-0000-3000-8000-000000000001" }
        }, null, 2)
      },
      {
        id: "rcon",
        label: "Source RCON TCP",
        body: JSON.stringify({
          tool: "mc_ops_rcon_execute",
          host: "127.0.0.1:25575",
          password: "[REDACTED]",
          command: "tps",
          ok: true,
          response: "TPS from last 1m, 5m, 15m: *20.0, *20.0, *20.0"
        }, null, 2)
      },
      {
        id: "backup",
        label: "Backup Integrity Audit",
        body: JSON.stringify({
          tool: "mc_hosting_backup_verify",
          panel_type: "pterodactyl",
          headless: true,
          policy: { max_age_hours: 24, min_size_bytes: 1024 },
          backup_count: 3,
          newest_backup: { name: "world-2026-11-24.tar.gz", size_bytes: 482910208, age_hours: 1.4 },
          issues: []
        }, null, 2)
      },
      {
        id: "html-qa",
        label: "HTML QA Proof Artifact",
        body: JSON.stringify({
          tool: "mc_qa_generate_html_report",
          verdict: "PASS",
          passed_stages: 4,
          total_stages: 4,
          snapshot_count: 1,
          preview_attached_as_mcp_image: true,
          written_path: "reports/qa-proof.html",
          secrets_redacted: true
        }, null, 2)
      },
      {
        id: "cloud-grid",
        label: "Cloud Fly.io 256MB Grid",
        body: JSON.stringify({
          tool: "mc_bot_generate_cloud_deploy",
          target: "fly_io",
          filename: "fly.mckit-bot.toml",
          bot_count: 5,
          estimated_ram_mb: 336,
          anti_oom_limit_mb: 420,
          screen_lock_free: true
        }, null, 2)
      },
      {
        id: "plugin-matrix",
        label: "Plugin Conflict Matrix",
        body: JSON.stringify({
          tool: "mc_audit_plugin_matrix",
          platform: "folia",
          status: "fail",
          findings: [
            { rule_id: "CONFLICT-AUTH", severity: "error", plugins: ["AuthMe.jar", "nLogin.jar"] },
            { rule_id: "CONFLICT-PACK", severity: "error", plugins: ["ItemsAdder.jar", "Nexo.jar"] },
            { rule_id: "MATRIX-002", severity: "error", missing_dependency: ["mythiclib"] }
          ]
        }, null, 2)
      },
      {
        id: "docker-stack",
        label: "Full-Stack Docker Bot Grid",
        body: JSON.stringify({
          tool: "mc_ops_generate_docker_stack",
          filename: "docker-compose.mckit-full.yml",
          server_type: "FOLIA",
          mc_version: "1.21.4",
          concurrent_bots: 10,
          bot_pool_mem_limit_mb: 548,
          visual_bot_mem_limit_mb: 1600,
          screen_lock_free: true
        }, null, 2)
      },
      {
        id: "rbac-auth",
        label: "RBAC & AuthMe Security",
        body: JSON.stringify({
          tool: "mc_audit_permissions_rbac + mc_bot_diagnose_auth_plugin",
          grade: "A",
          wildcards_blocked: true,
          password_hash: "ARGON2",
          auto_auth_template: "/login <env:MCKIT_BOT_PASS>",
          secrets_redacted: true
        }, null, 2)
      }
    ];
    function select(id) {
      tabs.querySelectorAll(".sc-chip").forEach(function (b) {
        b.classList.toggle("is-active", b.getAttribute("data-lab") === id);
      });
      var found = SAMPLES.find(function (s) { return s.id === id; }) || SAMPLES[0];
      out.textContent = found.body;
    }
    SAMPLES.forEach(function (s) {
      var btn = el("button", "sc-chip", s.label);
      btn.type = "button";
      btn.setAttribute("data-lab", s.id);
      btn.addEventListener("click", function () { select(s.id); });
      tabs.append(btn);
    });
    select("wire-login");
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
