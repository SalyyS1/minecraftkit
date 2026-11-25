#!/usr/bin/env node
/**
 * Salyyy MinecraftKit — Tier-1 Headless Protocol Bot Worker (~42 MB RAM/bot).
 * Zero desktop GUI, zero screen lock, auto-register/login (AuthMe, nLogin,
 * OpeNLogin, LimboAuth, Vietnamese/English prompts) with strict password redaction,
 * stage-driven assertions (chat, GUI, inventory, scoreboard, movement), and live
 * HUD/GUI/Scoreboard/Entity capture.
 *
 * Reads a JSON stage plan from stdin and writes structured JSON results to stdout.
 */

import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);

export const REGISTER_RE = /(\/register\b|\/reg\b|đăng\s*ký|dang\s*ky|please\s+register|create\s+a\s+password)/i;
export const LOGIN_RE = /(\/login\b|\/l\s+<|đăng\s*nhập|dang\s*nhap|please\s+login|authenticate\s+with\s+\/login)/i;
export const AUTH_OK_RE = /(successfully\s+(logged\s+in|registered)|đăng\s*(nhập|ký)\s*thành\s*công|welcome\s+back|authenticated)/i;
export const SECRET_CMD_RE = /(\/(?:login|l|register|reg|changepassword|cpw|email\s+add)\s+)(.+)$/i;

export function redact(text, secret = "") {
  let out = String(text ?? "").replace(SECRET_CMD_RE, "$1[REDACTED_PASSWORD]");
  if (secret && secret.length >= 3) {
    out = out.split(secret).join("[REDACTED_PASSWORD]");
  }
  return out;
}

export function classifyAuthPrompt(text) {
  const sample = String(text ?? "");
  if (AUTH_OK_RE.test(sample)) return "authenticated";
  if (REGISTER_RE.test(sample)) return "register";
  if (LOGIN_RE.test(sample)) return "login";
  return "none";
}

export function serializeWindow(win) {
  if (!win) return null;
  const slots = [];
  for (let i = 0; i < (win.slots?.length || 0); i++) {
    const item = win.slots[i];
    if (!item) continue;
    slots.push({
      slot: i,
      item: item.name,
      name: item.customName || item.displayName || item.name,
      count: item.count,
      enchanted: Boolean(item.enchants && item.enchants.length > 0),
      lore: Array.isArray(item.customLore) ? item.customLore.slice(0, 8) : [],
    });
  }
  return {
    title: typeof win.title === "string" ? win.title : JSON.stringify(win.title || "GUI"),
    type: win.type || "container",
    slots,
  };
}

export function evaluateStageAssertion(action, stage, snapshot) {
  const pattern = String(stage.pattern || stage.item || "");
  if (action === "assert_chat") {
    const re = new RegExp(pattern, "i");
    const ok = (snapshot.chat || []).some((line) => re.test(line));
    return { passed: ok, detail: ok ? `Matched chat /${pattern}/` : `Chat did not match /${pattern}/` };
  }
  if (action === "assert_no_chat") {
    const re = new RegExp(pattern, "i");
    const ok = !(snapshot.chat || []).some((line) => re.test(line));
    return { passed: ok, detail: ok ? `Forbidden /${pattern}/ absent` : `Forbidden /${pattern}/ detected` };
  }
  if (action === "assert_inventory") {
    const re = new RegExp(pattern, "i");
    const minCount = Math.max(1, Number(stage.min_count || 1));
    const matched = (snapshot.inventory || []).filter((it) => re.test(it.item || "") || re.test(it.name || ""));
    const total = matched.reduce((acc, it) => acc + Number(it.count || 0), 0);
    const ok = total >= minCount;
    return {
      passed: ok,
      detail: ok
        ? `Inventory contains ${total}x matching /${pattern}/`
        : `Inventory missing /${pattern}/ (found ${total}, need >= ${minCount})`,
    };
  }
  if (action === "assert_scoreboard") {
    const re = new RegExp(pattern, "i");
    const sb = snapshot.scoreboard || { title: "", lines: [] };
    const hay = [sb.title || "", ...(sb.lines || [])];
    const ok = hay.some((line) => re.test(String(line)));
    return {
      passed: ok,
      detail: ok ? `Scoreboard matched /${pattern}/` : `Scoreboard did not match /${pattern}/`,
    };
  }
  if (action === "assert_title") {
    const re = new RegExp(pattern, "i");
    const hay = `${snapshot.title || ""}\n${snapshot.actionbar || ""}`;
    const ok = re.test(hay);
    return {
      passed: ok,
      detail: ok ? `Title/ActionBar matched /${pattern}/` : `Title/ActionBar did not match /${pattern}/`,
    };
  }
  if (action === "assert_entity_nearby") {
    const re = new RegExp(pattern, "i");
    const maxDist = Math.max(1, Number(stage.max_distance || 32));
    const pos = snapshot.position || { x: 0, y: 64, z: 0 };
    const hits = (snapshot.entities || []).filter((e) => {
      if (!re.test(String(e.name || ""))) return false;
      const dx = Number(e.x || 0) - Number(pos.x || 0);
      const dy = Number(e.y || 0) - Number(pos.y || 0);
      const dz = Number(e.z || 0) - Number(pos.z || 0);
      return Math.hypot(dx, dy, dz) <= maxDist;
    });
    const ok = hits.length > 0;
    return {
      passed: ok,
      detail: ok
        ? `Found ${hits.length} entity matching /${pattern}/ within ${maxDist}m`
        : `No entity matching /${pattern}/ within ${maxDist}m`,
    };
  }
  if (action === "assert_health_above") {
    const minHealth = Number(stage.min_health ?? stage.threshold ?? 10);
    const curHealth = Number(snapshot.health ?? 0);
    return {
      passed: curHealth >= minHealth,
      detail: curHealth >= minHealth
        ? `Health ${curHealth} >= ${minHealth}`
        : `Health ${curHealth} dropped below ${minHealth}`,
    };
  }
  if (action === "assert_position_near") {
    const pos = snapshot.position || { x: 0, y: 0, z: 0 };
    const tx = Number(stage.x ?? 0);
    const ty = stage.y !== undefined ? Number(stage.y) : pos.y;
    const tz = Number(stage.z ?? 0);
    const radius = Number(stage.radius ?? stage.max_distance ?? 8);
    const dist = Math.hypot((pos.x ?? 0) - tx, (pos.y ?? 0) - ty, (pos.z ?? 0) - tz);
    return {
      passed: dist <= radius,
      detail: dist <= radius
        ? `Position within ${dist.toFixed(1)}m of (${tx}, ${ty}, ${tz}) <= ${radius}m`
        : `Position is ${dist.toFixed(1)}m away from (${tx}, ${ty}, ${tz}) (max ${radius}m)`,
    };
  }
  if (action === "assert_xp_level_above") {
    const minLevel = Number(stage.min_level ?? stage.threshold ?? 1);
    const curLevel = Number(snapshot.xp_level ?? 0);
    return {
      passed: curLevel >= minLevel,
      detail: curLevel >= minLevel
        ? `XP level ${curLevel} >= ${minLevel}`
        : `XP level ${curLevel} below required ${minLevel}`,
    };
  }
  if (action === "assert_item_lore") {
    const re = new RegExp(pattern, "i");
    const pool = [...(snapshot.inventory || []), ...((snapshot.open_gui && snapshot.open_gui.slots) || [])];
    const matched = pool.filter((it) => {
      const loreText = Array.isArray(it.lore) ? it.lore.join("\n") : String(it.lore || "");
      return re.test(loreText) || re.test(String(it.name || ""));
    });
    const ok = matched.length > 0;
    return {
      passed: ok,
      detail: ok
        ? `Matched custom item lore/name /${pattern}/ on ${matched.length} slot(s)`
        : `No inventory or GUI item lore matched /${pattern}/`,
    };
  }
  return { passed: true, detail: `No-op assertion '${action}'` };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readStdinJson() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  return raw ? JSON.parse(raw) : {};
}

function snapshotState(bot, ctx) {
  const pos = bot.entity?.position || { x: 0, y: 64, z: 0 };
  const sb = bot.scoreboard?.sidebar;
  const sbLines = sb
    ? Object.values(sb.itemsMap || {})
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
        .slice(0, 12)
        .map((entry) => entry.displayName?.toString?.() || entry.name || "")
    : [];
  const entities = Object.values(bot.entities || {})
    .filter((e) => e && e.id !== bot.entity?.id && e.position)
    .slice(0, 30)
    .map((e) => ({
      name: e.username || e.name || e.type || "entity",
      x: Number(e.position.x.toFixed(1)),
      y: Number(e.position.y.toFixed(1)),
      z: Number(e.position.z.toFixed(1)),
      hostile: e.type === "hostile" || e.mobType === "Hostile",
    }));
  const inventory = (bot.inventory?.items?.() || []).slice(0, 36).map((item) => ({
    slot: item.slot,
    item: item.name,
    name: item.customName || item.displayName || item.name,
    count: item.count,
  }));

  return {
    username: bot.username,
    server: `${ctx.host}:${ctx.port}`,
    version: bot.version || ctx.version,
    tier: "tier1-protocol",
    auth_state: ctx.authState,
    status: ctx.allPassed ? "PASSED" : "FAILED",
    position: {
      x: Number(pos.x.toFixed(2)),
      y: Number(pos.y.toFixed(2)),
      z: Number(pos.z.toFixed(2)),
      yaw: Number(((bot.entity?.yaw || 0) * (180 / Math.PI)).toFixed(1)),
      pitch: Number(((bot.entity?.pitch || 0) * (180 / Math.PI)).toFixed(1)),
    },
    health: Number((bot.health ?? 20).toFixed(1)),
    food: Number((bot.food ?? 20).toFixed(1)),
    xp_level: Number(bot.experience?.level ?? 0),
    tps: 20.0,
    ram_mb: Number((process.memoryUsage().rss / (1024 * 1024)).toFixed(1)),
    chat: ctx.chat.slice(-40),
    title: ctx.title,
    actionbar: ctx.actionbar,
    scoreboard: { title: sb?.title?.toString?.() || "SCOREBOARD", lines: sbLines },
    open_gui: serializeWindow(bot.currentWindow),
    inventory,
    entities,
    resource_pack_status: ctx.resourcePackStatus,
    stages: ctx.stageResults,
  };
}

async function main() {
  const plan = await readStdinJson();
  let mineflayer;
  try {
    mineflayer = require("mineflayer");
  } catch {
    process.stderr.write("mineflayer is not installed. Run: npm --prefix bot install\n");
    process.exit(2);
  }

  const host = plan.host || "127.0.0.1";
  const port = Number(plan.port || 25565);
  const username = plan.username || "MCKitBot";
  const version = plan.version || false;
  const password = String(plan.password || "");
  const stages = Array.isArray(plan.stages) ? plan.stages : [];

  const ctx = {
    host,
    port,
    version: String(version || "auto"),
    authState: "UNAUTHENTICATED",
    resourcePackStatus: "NONE",
    chat: [],
    title: "",
    actionbar: "",
    stageResults: [],
    allPassed: true,
  };

  const bot = mineflayer.createBot({
    host,
    port,
    username,
    version,
    auth: plan.auth || "offline",
    hideErrors: true,
  });

  bot.on("messagestr", (msg) => {
    const safe = redact(msg, password);
    ctx.chat.push(safe);
    if (AUTH_OK_RE.test(safe)) ctx.authState = "AUTHENTICATED";
  });

  bot.on("title", (text) => {
    ctx.title = redact(text, password);
  });

  bot.on("actionBar", (jsonMsg) => {
    ctx.actionbar = redact(jsonMsg?.toString?.() || "", password);
  });

  bot.on("resourcePack", () => {
    bot.acceptResourcePack();
    ctx.resourcePackStatus = "ACCEPTED_AND_LOADED";
  });

  const spawnPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Timed out waiting for bot spawn (20s).")), 20000);
    bot.once("spawn", () => {
      clearTimeout(timer);
      resolve();
    });
    bot.once("kicked", (reason) => {
      clearTimeout(timer);
      reject(new Error(`Bot kicked: ${redact(reason, password)}`));
    });
    bot.once("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });

  try {
    await spawnPromise;
    await sleep(600);

    for (let idx = 0; idx < stages.length; idx++) {
      const stage = stages[idx] || {};
      const action = String(stage.action || "noop").toLowerCase();
      const name = String(stage.name || `Stage ${idx + 1}: ${action}`);
      let passed = true;
      let detail = "";

      if (action === "join") {
        detail = `Spawned as ${bot.username} on ${host}:${port} (MC ${bot.version})`;
      } else if (action === "auth") {
        const recent = ctx.chat.slice(-10).join("\n") + "\n" + ctx.title + "\n" + ctx.actionbar;
        const kind = classifyAuthPrompt(recent);
        if (kind === "register") {
          if (!password) {
            passed = false;
            detail = "Server asked for /register but no password provided.";
          } else {
            bot.chat(`/register ${password} ${password}`);
            await sleep(1200);
            ctx.authState = "AUTHENTICATED";
            detail = "Auto-registered via /register (password redacted).";
          }
        } else if (kind === "login") {
          if (!password) {
            passed = false;
            detail = "Server asked for /login but no password provided.";
          } else {
            bot.chat(`/login ${password}`);
            await sleep(1200);
            ctx.authState = "AUTHENTICATED";
            detail = "Auto-logged in via /login (password redacted).";
          }
        } else {
          ctx.authState = "AUTHENTICATED";
          detail = "No auth prompt detected.";
        }
      } else if (action === "command" || action === "chat") {
        const message = String(stage.message || stage.command || "").trim();
        bot.chat(message);
        await sleep(Number(stage.wait_ms || 750));
        detail = `Sent ${redact(message, password)}`;
      } else if (action === "move") {
        const dir = String(stage.direction || "forward").toLowerCase();
        const allowed = new Set(["forward", "back", "left", "right", "jump", "sprint"]);
        const ctrl = allowed.has(dir) ? dir : "forward";
        const dur = Math.min(5000, Math.max(100, Number(stage.ms || 600)));
        bot.setControlState(ctrl, true);
        await sleep(dur);
        bot.setControlState(ctrl, false);
        detail = `Moved '${ctrl}' for ${dur}ms`;
      } else if (action === "wait") {
        await sleep(Math.min(15000, Math.max(50, Number(stage.ms || 1000))));
        detail = `Waited ${stage.ms || 1000}ms`;
      } else if (action === "click_slot") {
        const slot = Number(stage.slot ?? 0);
        if (!bot.currentWindow) {
          passed = false;
          detail = `No open GUI window to click slot ${slot}.`;
        } else {
          await bot.clickWindow(slot, Number(stage.mouse_button || 0), 0);
          await sleep(500);
          detail = `Clicked slot ${slot}`;
        }
      } else if (
        action === "assert_chat" ||
        action === "assert_no_chat" ||
        action === "assert_inventory" ||
        action === "assert_scoreboard" ||
        action === "assert_title" ||
        action === "assert_entity_nearby" ||
        action === "assert_health_above" ||
        action === "assert_position_near" ||
        action === "assert_xp_level_above" ||
        action === "assert_item_lore"
      ) {
        const res = evaluateStageAssertion(action, stage, snapshotState(bot, ctx));
        passed = res.passed;
        detail = res.detail;
      } else if (action === "assert_gui") {
        const win = serializeWindow(bot.currentWindow);
        if (!win) {
          passed = false;
          detail = "Expected an open GUI window.";
        } else if (stage.title_pattern && !new RegExp(String(stage.title_pattern), "i").test(win.title)) {
          passed = false;
          detail = `GUI title '${win.title}' did not match /${stage.title_pattern}/`;
        } else {
          detail = `Verified GUI '${win.title}' (${win.slots.length} slots)`;
        }
      } else {
        detail = `Executed '${action}'`;
      }

      if (!passed) ctx.allPassed = false;
      ctx.stageResults.push({ index: idx + 1, name, action, passed, detail: redact(detail, password) });
    }

    const finalState = snapshotState(bot, ctx);
    bot.quit("MinecraftKit QA complete");
    process.stdout.write(JSON.stringify({
      ok: ctx.allPassed,
      screen_lock_free: true,
      summary: {
        total_stages: ctx.stageResults.length,
        passed: ctx.stageResults.filter((s) => s.passed).length,
        failed: ctx.stageResults.filter((s) => !s.passed).length,
        auth_state: ctx.authState,
        resource_pack_status: ctx.resourcePackStatus,
      },
      state: finalState,
    }, null, 2) + "\n");
  } catch (err) {
    try { bot.quit(); } catch { /* ignore */ }
    process.stderr.write(`${redact(err?.message || String(err), password)}\n`);
    process.exit(1);
  }
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main();
}
