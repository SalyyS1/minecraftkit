(function () {
  "use strict";

  var PRESETS = {
    spark: [
      {
        label: "Collapsed: Sync JDBC + ModelEngine",
        threshold: 5.0,
        text: [
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;com.myrpg.guild.GuildListener.onJoin;com.zaxxer.hikari.pool.HikariPool.getConnection;com.mysql.cj.jdbc.ClientPreparedStatement.executeQuery 340",
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.server.level.ServerChunkCache.getChunk;com.myrpg.dungeon.RoomSpawner.loadArena 190",
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;com.ticxo.modelengine.core.tick.ModelTicker.tickBones 140",
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.world.entity.ai.goal.GoalSelector.tick 130",
          "Craft Async Scheduler Management Thread - 1;java.util.concurrent.ThreadPoolExecutor.runWorker;java.util.concurrent.ThreadPoolExecutor.getTask 200"
        ].join("\n")
      },
      {
        label: "Call-Tree: HikariCP Async Starvation",
        threshold: 5.0,
        text: [
          "Server thread 100.00% (5000ms)",
          "  |-- net.minecraft.server.MinecraftServer.tickChildren() 88.00% (4400ms)",
          "  |   |-- net.minecraft.world.level.block.entity.HopperBlockEntity.pushItemsTick() 34.00% (1700ms)",
          "  |   `-- net.Indyuce.mmoitems.listener.PlayerListener$$Lambda$0x00007f/0x12ab.lambda$onAttack$0() 18.50% (925ms)",
          "Folia Async Scheduler Thread #2 65.00% (3250ms)",
          "  `-- com.myrpg.economy.LedgerSync.flushBatch() 65.00% (3250ms)",
          "      `-- com.zaxxer.hikari.pool.HikariPool.getConnection() 64.00% (3200ms)"
        ].join("\n")
      },
      {
        label: "Clean Tick + Benign Idle Pool",
        threshold: 10.0,
        text: [
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.server.MinecraftServer.waitUntilNextTick 940",
          "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.server.level.ServerLevel.tick 60",
          "Folia Async Scheduler Thread #1;java.util.concurrent.ForkJoinPool.runWorker;java.util.concurrent.ForkJoinPool.scan 400"
        ].join("\n")
      }
    ],
    folia: [
      {
        label: "GlobalRegionScheduler Spatial Escape",
        domain: "auto",
        text: [
          "\"Global Region Scheduler\" #29 prio=5 os_prio=0 runnable",
          "    at net.minecraft.world.level.Level.getBlockAt(Level.java:412)",
          "    at org.bukkit.craftbukkit.block.CraftBlock.setType(CraftBlock.java:198)",
          "    at com.myrpg.events.MeteorBossTask.spawnCrater(MeteorBossTask.java:87)",
          "    at io.papermc.paper.threadedregions.scheduler.FoliaGlobalRegionScheduler$GlobalScheduledTask.run(FoliaGlobalRegionScheduler.java:144)"
        ].join("\n")
      },
      {
        label: "Multi-Thread: Async + Blocking .join()",
        domain: "auto",
        text: [
          "\"Folia Async Scheduler Thread #3\" #41 daemon prio=5 runnable",
          "    at org.bukkit.craftbukkit.entity.CraftPlayer.openInventory(CraftPlayer.java:512)",
          "    at net.Indyuce.mmoitems.gui.CraftingStationView.openAsync(CraftingStationView.java:64)",
          "    at io.papermc.paper.threadedregions.scheduler.FoliaAsyncScheduler$AsyncScheduledTask.run(FoliaAsyncScheduler.java:118)",
          "",
          "\"Region Scheduler Thread #1\" #24 prio=5 waiting",
          "    at java.base@25.0.1/java.util.concurrent.CompletableFuture.join(CompletableFuture.java:2118)",
          "    at com.myrpg.claim.RegionClaimService.verifyChunkOwner(RegionClaimService.java:103)",
          "    at io.papermc.paper.threadedregions.TickRegions$ConcreteRegionSection.tickRegion(TickRegions.java:390)"
        ].join("\n")
      },
      {
        label: "Clean Region + Entity Handoff",
        domain: "auto",
        text: [
          "\"Region Scheduler Thread #0\" #22 prio=5 runnable",
          "    at com.ticxo.modelengine.core.ModelUpdater.stepRegionModels(ModelUpdater.java:74)",
          "    at io.papermc.paper.threadedregions.TickRegions$ConcreteRegionSection.tickRegion(TickRegions.java:390)"
        ].join("\n")
      }
    ],
    protocol_sql: [
      {
        label: "Netty: Unbounded Serverbound + Skewed Codec",
        text: [
          "public record SpellCastPayload(int spellId, UUID caster, String macro, ItemStack icon) implements CustomPacketPayload {",
          "    public static final Type<SpellCastPayload> TYPE = new Type<>(ResourceLocation.fromNamespaceAndPath(\"MyRPG\", \"SpellCast\"));",
          "    public static final StreamCodec<FriendlyByteBuf, SpellCastPayload> CODEC = StreamCodec.of(",
          "        (buf, msg) -> { buf.writeVarInt(msg.spellId()); buf.writeUUID(msg.caster()); buf.writeUtf(msg.macro()); },",
          "        buf -> new SpellCastPayload(buf.readUUID().hashCode(), new UUID(0L, 0L), buf.readUtf(), null)",
          "    );",
          "    public void onPacketReceive(PacketReceiveEvent event, Player player) {",
          "        ByteBuf scratch = Unpooled.buffer(256);",
          "        player.getWorld().getBlockAt(0, 64, 0).setType(Material.DIAMOND_BLOCK);",
          "    }",
          "}"
        ].join("\n")
      },
      {
        label: "SQL: Sync JDBC + Leak + Folia Callback Escape",
        text: [
          "HikariConfig cfg = new HikariConfig();",
          "cfg.setJdbcUrl(\"jdbc:mysql://db.internal:3306/rpg\");",
          "cfg.setMaximumPoolSize(24);",
          "cfg.setMaxLifetime(1800000L);",
          "@EventHandler",
          "public void onPlayerJoin(PlayerJoinEvent event) {",
          "    Connection conn = dataSource.getConnection();",
          "    PreparedStatement ps = conn.prepareStatement(\"SELECT * FROM profiles WHERE name = '\" + event.getPlayer().getName() + \"'\");",
          "    ps.executeQuery();",
          "    CompletableFuture.supplyAsync(() -> loadKit(event.getPlayer().getUniqueId())).thenAccept(kit -> {",
          "        event.getPlayer().getInventory().addItem(kit);",
          "    });",
          "}"
        ].join("\n")
      },
      {
        label: "Clean Bounded RegistryCodec + Async .use{}",
        text: [
          "public static final CustomPacketPayload.Type<RuneSyncPayload> TYPE =",
          "    new CustomPacketPayload.Type<>(ResourceLocation.fromNamespaceAndPath(\"myrpg\", \"rune_sync\"));",
          "public static final StreamCodec<RegistryFriendlyByteBuf, RuneSyncPayload> CODEC = StreamCodec.composite(",
          "    ByteBufCodecs.VAR_INT, RuneSyncPayload::slot,",
            "    ByteBufCodecs.stringUtf8(64), RuneSyncPayload::runeId,",
          "    RuneSyncPayload::new",
          ");"
        ].join("\n")
      }
    ],
    chunk_jfr: [
      {
        label: "Moonrise: Sync Load + Join Deadlock + Ticket Leak",
        text: [
          "sync-chunk-writes=true",
          "region-file-compression=zlib",
          "plugin_tickets: 120",
          "public void teleportGuildRaid(World world, int cx, int cz, Plugin plugin) {",
          "    Chunk syncChunk = world.getChunkAt(cx + 2, cz);",
          "    world.addPluginChunkTicket(cx, cz, plugin);",
          "    BlockState[] tiles = syncChunk.getTileEntities();",
          "    world.locateNearestStructure(syncChunk.getBlock(0, 64, 0).getLocation(), StructureType.MINESHAFT, 64, false);",
          "    for (int i = 0; i < 32; i++) {",
          "        world.getChunkAtAsync(cx + i, cz).join();",
          "    }",
          "}"
        ].join("\n")
      },
      {
        label: "JFR + GC STW + Monitor Convoy + Region Skew",
        text: [
          "[12.200s] Tick #244 took 190.0ms",
          "[12.160s][info][gc] GC(18) Pause Young (Evacuation Failure) 95.0ms",
          "[12.195s][info][safepoint] Safepoint: Reaching safepoint: 24.5 ms",
          "jdk.JavaMonitorEnter { startTime = 12.040s, duration = 64.0 ms, monitorClass = com.myrpg.cache.GuildVaultLock, eventThread = \"Region Scheduler Thread #0\", previousOwner = \"Folia Async Scheduler Thread #2\" }",
          "jdk.FileForce { startTime = 12.050s, duration = 48.0 ms, eventThread = \"RegionFile I/O #0\" }",
          "jdk.VirtualThreadPinned { startTime = 12.080s, duration = 22.0 ms, eventThread = \"VirtualThread-44\" }",
          "Region Scheduler Thread #0;io.papermc.paper.threadedregions.TickRegions.tickRegion;java.util.concurrent.CompletableFuture.waitingGet 380",
          "Region Scheduler Thread #1;io.papermc.paper.threadedregions.TickRegions.tickRegion 20"
        ].join("\n")
      },
      {
        label: "Clean Async Chunk + LZ4 Healthy Pipeline",
        text: [
          "sync-chunk-writes=false",
          "region-file-compression=lz4",
          "world.getChunkAtAsync(cx, cz, true, false).thenAccept(chunk -> {",
          "    Bukkit.getRegionScheduler().execute(plugin, world, cx, cz, () -> {",
          "        chunk.getTileEntities(b -> b.getType() == Material.CHEST, false);",
          "    });",
          "});"
        ].join("\n")
      }
    ],
    bot_ops: [
      {
        label: "Hardcoded Password + Exposed RCON + MD5 AuthMe",
        text: [
          "online-mode=false",
          "server-ip=0.0.0.0",
          "enable-rcon=true",
          "rcon.password=admin123",
          "passwordHash: MD5",
          "bot_tier: desktop-full-client",
          "bot_count: 10",
          "stages:",
          "  - command: /login MyRawPassword99"
        ].join("\n")
      },
      {
        label: "Hardened Headless Bot Grid + Argon2 + Loopback",
        text: [
          "online-mode=false",
          "server-ip=127.0.0.1",
          "enable-rcon=false",
          "passwordHash: ARGON2",
          "bot_tier: tier1-protocol",
          "bot_count: 10",
          "password: env:MCKIT_BOT_PASS",
          "stages:",
          "  - action: auto_auth",
          "    redact_secrets: true"
        ].join("\n")
      }
    ],
    pack_cfg: [
      {
        label: "Lagging Paper Config + Legacy 1.20.1 Pack",
        text: [
          "sync-chunk-writes=true",
          "view-distance=16",
          "simulation-distance=12",
          "region-file-compression=zlib",
          "monsters: 90",
          "hopper-check: 1",
          "per-player-mob-spawns: false",
          "treasure-maps-find-already-discovered: false",
          "\"pack_format\": 15",
          "\"overrides\": [{\"predicate\": {\"custom_model_data\": 1001}}]"
        ].join("\n")
      },
      {
        label: "Tuned Folia/Paper LZ4 + Clean 1.21.4 Pack",
        text: [
          "sync-chunk-writes=false",
          "view-distance=10",
          "simulation-distance=6",
          "region-file-compression=lz4",
          "monsters: 45",
          "hopper-check: 3",
          "per-player-mob-spawns: true",
          "\"pack_format\": 46"
        ].join("\n")
      }
    ],
    mythic_mmo: [
      {
        label: "Lag-Bomb Boss Skill + Exploit Sword",
        text: [
          "LagBoss:",
          "  Type: WITHER_SKELETON",
          "  Health: 500",
          "  Skills:",
          "  - effect:particles{p=flame;amount=2500} @EIR{r=180} ~onTimer:1",
          "  - damage{amount=50} @PIR{r=120} ~onAttack",
          "BrokenSword:",
          "  base:",
          "    material: NETHERITE_SWORD",
          "    attack-damage: 999999",
          "    mana: -50"
        ].join("\n")
      },
      {
        label: "Clean Balanced MythicMobs FrostKnight",
        text: [
          "FrostKnight:",
          "  Type: STRAY",
          "  Health: 180",
          "  Skills:",
          "  - skill{s=FrostNova} @EIR{r=12} ~onTimer:40",
          "FrostNova:",
          "  Cooldown: 6",
          "  Skills:",
          "  - effect:particles{p=snowflake;amount=40} @Self",
          "  - damage{amount=12} @PIR{r=8} ~onAttack"
        ].join("\n")
      }
    ],
    skript_wg_eco: [
      {
        label: "Lagging Skript + Spawn Grief + Shop Dupe",
        text: [
          "every 1 tick:",
          "  loop all entities:",
          "    set {mob::%loop-entity%} to location of loop-entity",
          "    execute console command \"give %arg-1% diamond\"",
          "spawn:",
          "  priority: 0",
          "  flags:",
          "    pvp: allow",
          "    tnt: allow",
          "    passthrough: allow",
          "diamond_block:",
          "  buy: 100",
          "  sell: 250",
          "  starting-balance: 50000000"
        ].join("\n")
      },
      {
        label: "Clean Hardened Skript, Spawn & Economy",
        text: [
          "every 5 seconds:",
          "  loop all players:",
          "    send action bar \"Welcome\" to loop-player",
          "spawn:",
          "  priority: 10",
          "  flags:",
          "    pvp: deny",
          "    tnt: deny",
          "    mob-spawning: deny",
          "diamond_block:",
          "  buy: 450",
          "  sell: 180",
          "  starting-balance: 500",
          "  tax-rate: 5"
        ].join("\n")
      }
    ],
    plugin_spigot: [
      {
        label: "Legacy Spigot + Unsafe plugin.yml",
        text: [
          "settings:",
          "  bungeecord: true",
          "  restart-on-crash: true",
          "spawn-limits:",
          "  monsters: 120",
          "entity-activation-range:",
          "  monsters: 48",
          "name: LegacyAdminPlugin",
          "version: 1.0",
          "main: com.example.LegacyAdmin",
          "load: STARTUP",
          "permissions:",
          "  legacy.admin.*:",
          "    default: true"
        ].join("\n")
      },
      {
        label: "Clean Paper 1.21.4 + Folia plugin.yml",
        text: [
          "settings:",
          "  bungeecord: false",
          "spawn-limits:",
          "  monsters: 45",
          "entity-activation-range:",
          "  monsters: 24",
          "name: ModernRPGPlugin",
          "version: 2.1.0",
          "api-version: '1.21.4'",
          "folia-supported: true",
          "main: com.salyvn.rpg.ModernRPG",
          "permissions:",
          "  rpg.admin:",
          "    default: op"
        ].join("\n")
      }
    ],
    proxy_geyser_net: [
      {
        label: "Exposed Velocity + Offline Geyser + Weak AntiCheat",
        text: [
          "online-mode = false",
          "player-info-forwarding-mode = \"legacy\"",
          "forwarding-secret = \"changeme\"",
          "bedrock:",
          "  port: 19132",
          "remote:",
          "  auth-type: offline",
          "mtu: 1492",
          "anticheat:",
          "  exempt-ops: true",
          "  verbose: true"
        ].join("\n")
      },
      {
        label: "Hardened Velocity Modern + Floodgate + GrimAC",
        text: [
          "online-mode = true",
          "player-info-forwarding-mode = \"modern\"",
          "forwarding-secret-file = \"forwarding.secret\"",
          "bedrock:",
          "  port: 19132",
          "remote:",
          "  auth-type: floodgate",
          "mtu: 1400",
          "anticheat:",
          "  exempt-ops: false",
          "  verbose: false"
        ].join("\n")
      }
    ]
  };

  var RPG_PREFIXES = [
    ["com.ticxo.modelengine", "ModelEngine"],
    ["net.Indyuce.mmoitems", "MMOItems"],
    ["net.indyuce.mmoitems", "MMOItems"],
    ["net.Indyuce.mmocore", "MMOCore"],
    ["net.Indyuce.mmoinventory", "MMOInventory"],
    ["fr.phoenixdevt.mmoprofiles", "MMOProfiles"],
    ["io.lumine.mythiccrucible", "MythicCrucible"],
    ["net.playavalon.mythicdungeons", "MythicDungeons"],
    ["io.lumine.mythicenchants", "MythicEnchants"],
    ["io.lumine.mythicrpg", "MythicRPG"],
    ["io.lumine.mythic.core", "CoreTools"]
  ];

  var ENGINE_PREFIXES = [
    "net.minecraft.", "com.mojang.", "io.papermc.", "ca.spottedleaf.",
    "org.bukkit.", "org.spigotmc.", "java.", "javax.", "jdk.", "sun.",
    "io.netty.", "it.unimi.", "com.zaxxer.hikari.", "com.mysql.",
    "org.mariadb.", "org.postgresql.", "org.sqlite.", "okhttp3."
  ];

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function demangleFrame(raw) {
    return raw
      .trim()
      .replace(/^at\s+/, "")
      .replace(/^[a-zA-Z0-9_.]+@[0-9A-Za-z_.+-]+\//, "")
      .replace(/\$\$Lambda(?:\$0x[0-9a-fA-F]+)?(?:\/0x[0-9a-fA-F]+)?/g, "::Lambda")
      .replace(/\.lambda\$([A-Za-z0-9_$]+)\$\d+/g, "::lambda$$$1")
      .replace(/\([^)]*\)$/, "()");
  }

  function attributeOwner(frame) {
    var i;
    for (i = 0; i < RPG_PREFIXES.length; i += 1) {
      if (frame.indexOf(RPG_PREFIXES[i][0]) === 0) {
        return { kind: "indexed_rpg_plugin", plugin: RPG_PREFIXES[i][1] };
      }
    }
    for (i = 0; i < ENGINE_PREFIXES.length; i += 1) {
      if (frame.indexOf(ENGINE_PREFIXES[i]) === 0) {
        return { kind: "engine", plugin: null };
      }
    }
    var m = /^([a-z][a-z0-9_]*)\.([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\.[A-Z]/.exec(frame);
    if (m) {
      return { kind: "third_party_plugin", plugin: m[2] };
    }
    return { kind: "runtime", plugin: null };
  }

  function isAsyncThread(name) {
    var low = name.toLowerCase();
    return low.indexOf("async scheduler") >= 0 ||
      low.indexOf("craft async") >= 0 ||
      low.indexOf("folia async") >= 0 ||
      low.indexOf("forkjoinpool") >= 0;
  }

  function isThreadHeader(label) {
    var low = label.toLowerCase();
    return low.indexOf("server thread") >= 0 ||
      low.indexOf("region scheduler") >= 0 ||
      low.indexOf("global region") >= 0 ||
      low.indexOf("entity scheduler") >= 0 ||
      isAsyncThread(low) ||
      low.indexOf("netty ") >= 0;
  }

  function analyzeSpark(rawText, thresholdPct) {
    var lines = rawText.split(/\r?\n/).filter(function (l) {
      var s = l.trim();
      return s.length > 0 && s.charAt(0) !== "#";
    });
    var collapsedRe = /^([^;\s][^;]*(?:;[^;]+)+)\s+([0-9]+(?:\.[0-9]+)?)\s*$/;
    var collapsedHits = lines.filter(function (l) { return collapsedRe.test(l.trim()); }).length;
    var isCollapsed = collapsedHits >= Math.max(1, Math.floor(lines.length / 2));

    var samples = [];
    var inc = {};
    var selfW = {};
    var callers = {};
    var threads = {};
    var totalWeight = 0;

    if (isCollapsed) {
      lines.forEach(function (ln) {
        var m = collapsedRe.exec(ln.trim());
        if (!m) { return; }
        var w = parseFloat(m[2]);
        if (!(w > 0)) { return; }
        var parts = m[1].split(";").map(function (p) { return p.trim(); }).filter(Boolean);
        var threadName = "Server thread";
        if (parts.length > 1 && isThreadHeader(parts[0])) {
          threadName = parts[0];
          parts = parts.slice(1);
        }
        var frames = parts.map(demangleFrame);
        totalWeight += w;
        samples.push({ thread: threadName, frames: frames, weight: w });
        var seen = {};
        var activePlugin = null;
        frames.forEach(function (fr) {
          var own = attributeOwner(fr);
          if (own.plugin) { activePlugin = own.plugin; }
          if (!seen[fr]) {
            seen[fr] = true;
            inc[fr] = (inc[fr] || 0) + w;
          }
          threads[fr] = threadName;
          if (activePlugin && !callers[fr]) { callers[fr] = activePlugin; }
        });
        var leaf = frames[frames.length - 1];
        selfW[leaf] = (selfW[leaf] || 0) + w;
      });
    } else {
      var nodes = [];
      var stack = [];
      var preRe = /^\[?\s*([0-9]+(?:\.[0-9]+)?)%\s*\]?\s*(?:\([0-9.,]+\s*(?:ms|s|samples)?\)\s*)?(.+?)\s*$/;
      var sufRe = /^(.+?)\s+([0-9]+(?:\.[0-9]+)?)%\s*(?:\([0-9.,]+\s*(?:ms|s|samples)?\))?\s*$/;

      lines.forEach(function (ln) {
        var pm = /^([\s\u2502|\u251c\u2514\u2500+`\\-]*)/.exec(ln);
        var prefix = pm ? pm[1] : "";
        var body = ln.slice(prefix.length).trim();
        if (!body) { return; }
        var depth = prefix.length;
        var pct = null;
        var label = body;
        var a = preRe.exec(body);
        var b = !a ? sufRe.exec(body) : null;
        if (a) { pct = parseFloat(a[1]); label = a[2]; }
        else if (b) { label = b[1]; pct = parseFloat(b[2]); }
        if (pct === null) { return; }
        while (stack.length > 0 && nodes[stack[stack.length - 1]].depth >= depth) {
          stack.pop();
        }
        var parent = stack.length > 0 ? stack[stack.length - 1] : null;
        var clean = label.replace(/^"|"$/g, "");
        var isRoot = parent === null && isThreadHeader(clean);
        var idx = nodes.length;
        nodes.push({ idx: idx, depth: depth, label: clean, frame: isRoot ? clean : demangleFrame(clean), isRoot: isRoot, weight: pct, parent: parent, children: [] });
        if (parent !== null) { nodes[parent].children.push(idx); }
        stack.push(idx);
      });

      nodes.forEach(function (n) {
        if (n.parent === null && !isAsyncThread(n.label)) {
          totalWeight += n.weight;
        }
      });
      if (!(totalWeight > 0)) { totalWeight = 100; }

      nodes.forEach(function (n) {
        if (n.isRoot && n.children.length > 0) { return; }
        var childSum = n.children.reduce(function (acc, c) { return acc + nodes[c].weight; }, 0);
        var sw = Math.max(0, n.weight - childSum);
        var chain = [];
        var cur = n.idx;
        while (cur !== null) { chain.unshift(nodes[cur]); cur = nodes[cur].parent; }
        var thr = chain[0].isRoot ? chain[0].label : "Server thread";
        var frs = chain.filter(function (x) { return !x.isRoot; }).map(function (x) { return x.frame; });
        if (!frs.length) { return; }
        var leaf = frs[frs.length - 1];
        inc[leaf] = (inc[leaf] || 0) + n.weight;
        selfW[leaf] = (selfW[leaf] || 0) + sw;
        threads[leaf] = thr;
        frs.forEach(function (f) {
          var own = attributeOwner(f);
          if (own.plugin && !callers[leaf]) { callers[leaf] = own.plugin; }
        });
        if (sw > 0 || n.children.length === 0) {
          samples.push({ thread: thr, frames: frs, weight: Math.max(sw, 0.01) });
        }
      });
    }

    if (!(totalWeight > 0)) { totalWeight = 100; }
    var findings = [];
    var seenRule = {};

    function pushFinding(ruleId, sev, frame, pct, plugin, msg, fix) {
      var key = ruleId + ":" + (plugin || frame);
      if (seenRule[key]) { return; }
      seenRule[key] = true;
      findings.push({ rule_id: ruleId, severity: sev, frame: frame, pct: Number(pct.toFixed(1)), plugin: plugin || null, message: msg, remediation: fix });
    }

    Object.keys(inc).sort(function (a, b) { return inc[b] - inc[a]; }).forEach(function (fr) {
      var incPct = Math.min(100, (inc[fr] / totalWeight) * 100);
      var selfPct = Math.min(100, ((selfW[fr] || 0) / totalWeight) * 100);
      var thr = threads[fr] || "Server thread";
      if (isAsyncThread(thr) || Math.max(incPct, selfPct) < thresholdPct) { return; }
      var low = fr.toLowerCase();
      var plug = callers[fr] || attributeOwner(fr).plugin;

      if (low.indexOf("serverchunkcache.getchunk") >= 0 || low.indexOf("syncload") >= 0 || low.indexOf("getchunkat") >= 0) {
        pushFinding("SPARK-001", "critical", fr, incPct, plug,
          "Synchronous chunk load '" + fr + "' consumes " + incPct.toFixed(1) + "% on " + thr + (plug ? " (plugin: " + plug + ")." : "."),
          "Switch to World.getChunkAtAsync(x, z).thenAccept(...) and pre-generate worlds.");
      } else if (low.indexOf("hikaripool") >= 0 || low.indexOf("java.sql.") >= 0 || low.indexOf("mysql") >= 0 || low.indexOf("sqlite") >= 0 || low.indexOf("socketread") >= 0) {
        pushFinding("SPARK-002", "critical", fr, incPct, plug,
          "Synchronous JDBC or network I/O '" + fr + "' blocks " + thr + " for " + incPct.toFixed(1) + "%" + (plug ? " (initiated by " + plug + ")." : "."),
          "Dispatch database and HTTP queries on Bukkit.getAsyncScheduler() and hop back to RegionScheduler/EntityScheduler.");
      } else if (low.indexOf("goalselector") >= 0 || low.indexOf("pathnavigation") >= 0 || low.indexOf("voxelshapes") >= 0) {
        pushFinding("SPARK-003", "high", fr, incPct, plug,
          "Entity AI or collision hotspot '" + fr + "' takes " + incPct.toFixed(1) + "% tick budget.",
          "Tune entity-activation-range and max-entity-collisions in paper-world-defaults.yml.");
      } else if (low.indexOf("hopperblockentity") >= 0 || low.indexOf("boundtickingblockentity") >= 0) {
        pushFinding("SPARK-004", "high", fr, incPct, plug,
          "Hopper or block-entity tick '" + fr + "' takes " + incPct.toFixed(1) + "% tick budget.",
          "Enable hopper.disable-move-event when InventoryMoveItemEvent is unused and raise ticks-per.hopper-check.");
      } else if (attributeOwner(fr).plugin && selfPct >= thresholdPct) {
        pushFinding("SPARK-007", "high", fr, selfPct, attributeOwner(fr).plugin,
          "Plugin hotspot '" + fr + "' (" + attributeOwner(fr).plugin + ") consumes " + selfPct.toFixed(1) + "% self time.",
          "Cache component/reflection lookups and debounce high-frequency event listeners.");
      }
    });

    var idleWorkers = 0;
    samples.forEach(function (s) {
      if (!isAsyncThread(s.thread)) { return; }
      var joined = s.frames.join(";").toLowerCase();
      var plug = null;
      s.frames.forEach(function (f) { var o = attributeOwner(f); if (o.plugin) { plug = o.plugin; } });
      var isIdle = (joined.indexOf("gettask") >= 0 || joined.indexOf("delayedworkqueue.take") >= 0 || joined.indexOf("forkjoinpool.scan") >= 0) && !plug;
      if (isIdle) { idleWorkers += 1; return; }
      if (joined.indexOf("hikaripool.getconnection") >= 0) {
        pushFinding("SPARK-008", "critical", s.frames[s.frames.length - 1], (s.weight / totalWeight) * 100, plug,
          "Async worker '" + s.thread + "' starved on HIKARICP_POOL_EXHAUSTION" + (plug ? " in " + plug : "") + ".",
          "Close leaked SQL connections, index slow queries, and align Hikari maximumPoolSize.");
      }
    });

    return {
      tool: "mc_audit_spark_flamegraph",
      status: findings.length ? "fail" : "pass",
      profile_format: isCollapsed ? "collapsed" : "call_tree",
      samples_analyzed: samples.length,
      benign_idle_workers: idleWorkers,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzeFolia(rawText, declaredDomain) {
    var lines = rawText.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var blocks = [];
    var curHeader = null;
    var curLines = [];

    lines.forEach(function (ln) {
      var m = /^"([^"]+)"/.exec(ln);
      if (m) {
        if (curLines.length || curHeader) { blocks.push({ header: curHeader || "Trace Snippet", lines: curLines }); }
        curHeader = m[1];
        curLines = [];
      } else {
        curLines.push(demangleFrame(ln));
      }
    });
    if (curLines.length || curHeader) {
      blocks.push({ header: curHeader || "Trace Snippet", lines: curLines });
    }

    var findings = [];
    var domains = [];

    blocks.forEach(function (b) {
      var lowH = b.header.toLowerCase();
      var joined = b.lines.join(" ").toLowerCase();
      var domain = declaredDomain !== "auto" ? declaredDomain.toUpperCase() : (
        lowH.indexOf("netty") >= 0 || joined.indexOf("epolleventloop") >= 0 ? "NETTY" :
        lowH.indexOf("global region") >= 0 || joined.indexOf("globalregionscheduler") >= 0 ? "GLOBAL" :
        joined.indexOf("entityscheduler") >= 0 ? "ENTITY" :
        lowH.indexOf("region scheduler") >= 0 || joined.indexOf("tickregions") >= 0 ? "REGION" :
        isAsyncThread(lowH) || joined.indexOf("foliaasyncscheduler") >= 0 ? "ASYNC" : "UNKNOWN"
      );
      if (domains.indexOf(domain) < 0) { domains.push(domain); }

      var plug = null;
      b.lines.forEach(function (fr) { var own = attributeOwner(fr); if (!plug && own.plugin) { plug = own.plugin; } });

      b.lines.forEach(function (fr) {
        var low = fr.toLowerCase();
        var isSpatial = low.indexOf("getblockat") >= 0 || low.indexOf("settype") >= 0 || low.indexOf("getchunkat") >= 0 ||
          low.indexOf("openinventory") >= 0 || low.indexOf("spawnentity") >= 0 || low.indexOf(".damage(") >= 0;

        if (low.indexOf("bukkit.getscheduler()") >= 0 || low.indexOf("bukkitrunnable.runtask") >= 0) {
          findings.push({
            rule_id: "FOLIA-TRC-006", severity: "critical", frame: fr, plugin: plug, domain: domain,
            message: "Legacy BukkitScheduler call '" + fr + "' throws UnsupportedOperationException on Folia.",
            remediation: "Dispatch onto RegionScheduler, EntityScheduler, GlobalRegionScheduler, or AsyncScheduler."
          });
        }
        if (domain === "ASYNC" && isSpatial) {
          findings.push({
            rule_id: "FOLIA-TRC-001", severity: "critical", frame: fr, plugin: plug, domain: domain,
            message: "ASYNC thread '" + b.header + "' mutates or reads regional world/entity state at '" + fr + "'.",
            remediation: "Marshal world work to Bukkit.getRegionScheduler().execute(...) or entity work to entity.getScheduler().run(...)."
          });
        }
        if (domain === "GLOBAL" && isSpatial) {
          findings.push({
            rule_id: "FOLIA-TRC-002", severity: "critical", frame: fr, plugin: plug, domain: domain,
            message: "GlobalRegionScheduler accesses spatial chunk/block/entity state at '" + fr + "' (owns zero chunks/entities).",
            remediation: "Route spatial coordinates through Bukkit.getRegionScheduler().execute(plugin, world, chunkX, chunkZ, task)."
          });
        }
        if ((domain === "REGION" || domain === "ENTITY") && (low.indexOf("getonlineplayers") >= 0 || (low.indexOf(".teleport(") >= 0 && low.indexOf("teleportasync") < 0))) {
          findings.push({
            rule_id: "FOLIA-TRC-003", severity: "high", frame: fr, plugin: plug, domain: domain,
            message: domain + " thread performs cross-region player iteration or synchronous teleport at '" + fr + "'.",
            remediation: "Use entity.teleportAsync(loc) and dispatch per-player mutations via player.getScheduler().run(...)."
          });
        }
        if (domain === "NETTY" && isSpatial) {
          findings.push({
            rule_id: "FOLIA-TRC-004", severity: "critical", frame: fr, plugin: plug, domain: domain,
            message: "Netty EventLoop accesses live world/entity state directly at '" + fr + "'.",
            remediation: "Copy packet payload into an immutable value and schedule onto player.getScheduler()."
          });
        }
        if ((domain === "REGION" || domain === "ENTITY" || domain === "GLOBAL") && (low.indexOf("completablefuture.join") >= 0 || low.indexOf("futuretask.get") >= 0)) {
          findings.push({
            rule_id: "FOLIA-TRC-005", severity: "critical", frame: fr, plugin: plug, domain: domain,
            message: "Tick domain " + domain + " blocks synchronously on '" + fr + "', risking a region merge barrier deadlock.",
            remediation: "Chain .thenAccept(...) asynchronously and hop back to RegionScheduler or EntityScheduler."
          });
        }
      });
    });

    return {
      tool: "mc_analyze_folia_scheduler_trace",
      status: findings.length ? "fail" : "pass",
      threads_analyzed: blocks.length,
      domains_detected: domains,
      finding_count: findings.length,
      findings: findings
    };
  }

  function varintBytes(n) {
    if (n < 128) { return 1; }
    if (n < 16384) { return 2; }
    if (n < 2097152) { return 3; }
    if (n < 268435456) { return 4; }
    return 5;
  }

  function analyzeProtocolAndSql(raw) {
    var findings = [];
    var src = String(raw || "");
    var low = src.toLowerCase();
    var maxWireBytes = 0;

    var mChan = src.match(/(?:ResourceLocation\.fromNamespaceAndPath|Key\.key)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)/);
    if (mChan) {
      var ns = mChan[1];
      var pathPart = mChan[2];
      var chan = ns + ":" + pathPart;
      maxWireBytes += varintBytes(chan.length) + chan.length;
      if (!/^[a-z0-9_.-]+$/.test(ns) || !/^[a-z0-9/._-]+$/.test(pathPart)) {
        findings.push({
          rule_id: "NETTY-005", severity: "high", frame: chan, domain: "NETTY",
          message: "Channel '" + chan + "' violates lowercase ResourceLocation character rules and throws ResourceLocationException.",
          remediation: "Normalize CustomPacketPayload.Type namespace and path to lowercase [a-z0-9_.-] and [a-z0-9/._-]."
        });
      }
    }

    var utfMatches = src.match(/ByteBufCodecs\.STRING_UTF8|\.readUtf\s*\(\s*\)/g);
    if (utfMatches) {
      var ub = varintBytes(32767 * 3) + 32767 * 3;
      maxWireBytes += ub * utfMatches.length;
      findings.push({
        rule_id: "NETTY-001", severity: "critical", frame: "readUtf/STRING_UTF8", domain: "NETTY",
        message: "Unbounded UTF-8 decode permits up to " + ub + " wire bytes per field on serverbound Netty path.",
        remediation: "Use ByteBufCodecs.stringUtf8(maxChars) or buf.readUtf(maxChars) with an explicit bound."
      });
    }
    var boundedUtf = /ByteBufCodecs\.stringUtf8\s*\(\s*(\d+)\s*\)|\.readUtf\s*\(\s*(\d+)\s*\)/g;
    var bm;
    while ((bm = boundedUtf.exec(src)) !== null) {
      var nChars = parseInt(bm[1] || bm[2], 10);
      maxWireBytes += varintBytes(nChars * 3) + nChars * 3;
    }
    if (maxWireBytes > 32767) {
      findings.push({
        rule_id: "NETTY-002", severity: "critical", frame: "ServerboundCustomPayloadPacket", domain: "NETTY",
        message: "Worst-case wire size (" + maxWireBytes + " B) exceeds 32,767 B serverbound custom payload cap.",
        remediation: "Cap string/array lengths so worst-case wire size stays <= 32,767 bytes."
      });
    }

    var writes = (src.match(/\.write(VarInt|VarLong|Int|Long|Utf|UUID|BlockPos|ByteArray)\s*\(/g) || []).map(function (s) { return s.replace(/^\.write|\($|\s+/g, "").toLowerCase(); });
    var reads = (src.match(/\.read(VarInt|VarLong|Int|Long|Utf|UUID|BlockPos|ByteArray)\s*\(/g) || []).map(function (s) { return s.replace(/^\.read|\($|\s+/g, "").toLowerCase(); });
    if (writes.length && reads.length && writes.join(",") !== reads.join(",")) {
      findings.push({
        rule_id: "NETTY-006", severity: "critical", frame: "encode/decode", domain: "NETTY",
        message: "Manual write order [" + writes.join(", ") + "] mismatches read order [" + reads.join(", ") + "], corrupting readerIndex.",
        remediation: "Use StreamCodec.composite(...) or align write* and read* calls in identical order."
      });
    }

    if ((low.indexOf("onpacketreceive") >= 0 || low.indexOf("channelread") >= 0) && (low.indexOf("getblockat") >= 0 || low.indexOf("settype") >= 0) && low.indexOf("getscheduler") < 0) {
      findings.push({
        rule_id: "NETTY-003", severity: "critical", frame: "NettyPacketHandler", domain: "NETTY",
        message: "Netty EventLoop listener mutates live world state directly without RegionScheduler or EntityScheduler handoff.",
        remediation: "Decode into an immutable record on Netty I/O, then dispatch via player.getScheduler().run(...)."
      });
    }

    if (/Unpooled\.(?:buffer|directBuffer)|\.retainedSlice\s*\(/.test(src) && !/release\s*\(/.test(src)) {
      findings.push({
        rule_id: "NETTY-004", severity: "high", frame: "Unpooled.buffer", domain: "NETTY",
        message: "ByteBuf allocated or retained without matching ReferenceCountUtil.safeRelease() in finally block.",
        remediation: "Release temporary ByteBuf instances inside try/finally to avoid direct memory leaks."
      });
    }

    if (low.indexOf("@eventhandler") >= 0 && low.indexOf("getconnection(") >= 0 && low.indexOf("supplyasync(") < 0) {
      findings.push({
        rule_id: "SQL-001", severity: "critical", frame: "EventHandler", domain: "SQL",
        message: "Synchronous JDBC getConnection/executeQuery runs on tick thread inside EventHandler.",
        remediation: "Offload JDBC queries to CompletableFuture.supplyAsync(..., dbExecutor) or AsyncScheduler."
      });
    } else if (low.indexOf("@eventhandler") >= 0 && low.indexOf("executequery(") >= 0) {
      var idxConn = low.indexOf("getconnection(");
      var idxAsync = low.indexOf("supplyasync(");
      if (idxConn >= 0 && (idxAsync < 0 || idxConn < idxAsync)) {
        findings.push({
          rule_id: "SQL-001", severity: "critical", frame: "EventHandler", domain: "SQL",
          message: "Synchronous JDBC getConnection/executeQuery executes before async boundary inside EventHandler.",
          remediation: "Move getConnection() inside CompletableFuture.supplyAsync(..., dbExecutor)."
        });
      }
    }

    if (/getConnection\s*\(/.test(src) && !/\btry\s*\([^)]*getConnection/.test(src) && src.indexOf(".use") < 0) {
      findings.push({
        rule_id: "SQL-004", severity: "critical", frame: "Connection", domain: "SQL",
        message: "JDBC Connection acquired without Java try-with-resources or Kotlin .use {}, leaking HikariPool slots.",
        remediation: "Wrap getConnection() and prepareStatement() inside try (...) { ... } or .use { ... }."
      });
    }

    if (/prepareStatement\s*\(\s*"[^"]*(?:SELECT|INSERT|UPDATE|DELETE)[^"]*"\s*\+/i.test(src)) {
      findings.push({
        rule_id: "SQL-005", severity: "critical", frame: "prepareStatement", domain: "SQL",
        message: "SQL query concatenates untrusted runtime strings instead of '?' bind parameters.",
        remediation: "Use parameterized '?' placeholders and PreparedStatement#setString."
      });
    }

    if (low.indexOf("thenaccept(") >= 0 && low.indexOf("getinventory()") >= 0 && low.indexOf("getscheduler().run") < 0) {
      findings.push({
        rule_id: "SQL-006", severity: "critical", frame: "CompletableFuture.thenAccept", domain: "SQL",
        message: "Async DB completion callback mutates Player inventory on worker thread without EntityScheduler hop.",
        remediation: "Marshal post-query Bukkit/Folia mutations onto player.getScheduler().run(plugin, task -> ..., null)."
      });
    }

    return {
      tool: "mc_audit_packet_codec+mc_audit_sql_persistence",
      status: findings.length ? "fail" : "pass",
      max_wire_bytes: maxWireBytes,
      wire_cap_bytes: 32767,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzeChunkAndJfr(src) {
    var findings = [];
    var low = src.toLowerCase();
    var pinnedTickets = 0;
    var tktMatch = src.match(/plugin[_ -]?tickets?\s*[:=]\s*(\d+)/i);
    if (tktMatch) { pinnedTickets = parseInt(tktMatch[1], 10); }
    var pinnedRamMb = Math.round(pinnedTickets * 25 * 0.09375 * 10) / 10;

    if (/\.(?:getChunkAt\s*\(|getChunk\s*\(\s*\)|loadChunk\s*\()/.test(src)) {
      findings.push({
        rule_id: "CHUNK-IO-001", severity: "critical", frame: "World.getChunkAt", domain: "CHUNK-IO",
        message: "Synchronous chunk load stalls tick thread behind Moonrise I/O and worldgen barriers.",
        remediation: "Switch to world.getChunkAtAsync(x, z, true).thenAccept(...) and marshal work onto RegionScheduler."
      });
    }
    if (/(?:getChunkAtAsync|teleportAsync)\s*\([^;]*?\)\s*\.\s*(?:join|get)\s*\(/.test(src)) {
      findings.push({
        rule_id: "CHUNK-IO-002", severity: "critical", frame: "CompletableFuture.join", domain: "CHUNK-IO",
        message: "Blocking .join()/.get() on async chunk future risks Moonrise task-queue barrier self-deadlock.",
        remediation: "Attach non-blocking .thenAccept(...) continuations instead of blocking the calling thread."
      });
    }
    if ((/addPluginChunkTicket\s*\(/.test(src) && !/removePluginChunkTicket/.test(src)) || pinnedTickets > 80) {
      findings.push({
        rule_id: "CHUNK-IO-003", severity: "high", frame: "PluginChunkTicket", domain: "CHUNK-IO",
        message: "Unreleased plugin chunk tickets pin resident chunks (25 chunks / ~2.34 MiB per level-31 ticket).",
        remediation: "Release tickets on expiry and invoke world.removePluginChunkTickets(plugin) in onDisable()."
      });
    }
    if (/\b(?:for|while)\s*\([^)]*\)\s*\{[\s\S]*?(?:getChunkAtAsync|teleportAsync)/.test(src) && low.indexOf("semaphore") < 0) {
      findings.push({
        rule_id: "CHUNK-IO-004", severity: "high", frame: "BatchChunkLoop", domain: "CHUNK-IO",
        message: "Unbounded async chunk burst saturates Moonrise worker queues (rho >= 1.0).",
        remediation: "Bound concurrent loads behind a Semaphore (4-8 permits) and pass urgent=false."
      });
    }
    if (/sync-chunk-writes\s*[=:]\s*true/i.test(src) || /region-file-compression\s*[=:]\s*(?:zlib|none)/i.test(src)) {
      findings.push({
        rule_id: "CHUNK-IO-005", severity: "high", frame: "RegionFileStorage", domain: "CHUNK-IO",
        message: "sync-chunk-writes=true or non-LZ4 region compression inflates Moonrise sector write/decode latency.",
        remediation: "Set sync-chunk-writes=false and region-file-compression=lz4 in server.properties."
      });
    }
    if (/(?:getChunkAt|getBlockAt)\s*\([^)]*[+-]\s*[1-9]\d*/.test(src) && low.indexOf("getregionscheduler()") < 0) {
      findings.push({
        rule_id: "CHUNK-IO-006", severity: "critical", frame: "RegionNeighborhood", domain: "FOLIA-CHUNK",
        message: "Neighbor chunk offset can cross Folia 16x16-chunk region-section boundary without ownership check.",
        remediation: "Guard neighbor access with Bukkit.isOwnedByCurrentRegion(loc) or dispatch via RegionScheduler."
      });
    }
    if (low.indexOf("locateneareststructure(") >= 0 || low.indexOf("locatenearestbiome(") >= 0) {
      findings.push({
        rule_id: "CHUNK-IO-007", severity: "high", frame: "World.locateNearestStructure", domain: "CHUNK-IO",
        message: "Synchronous structure/biome lookup scans ungenerated region headers on the tick thread.",
        remediation: "Pre-index structure coordinates offline or cap radius <= 16 chunks with result caching."
      });
    }
    if (/\.getTileEntities\s*\(\s*\)/.test(src)) {
      findings.push({
        rule_id: "CHUNK-IO-008", severity: "medium", frame: "Chunk.getTileEntities()", domain: "CHUNK-IO",
        message: "No-arg getTileEntities() clones full NBT BlockState snapshots for every tile in the chunk.",
        remediation: "Use chunk.getTileEntities(predicate, false) to avoid defensive snapshot cloning."
      });
    }

    var gcPauseMs = 0;
    var gcM = src.match(/Pause Young[^\n]*?(\d+(?:\.\d+)?)\s*ms/i) || src.match(/Allocation Stall[^\n]*?(\d+(?:\.\d+)?)\s*ms/i);
    if (gcM) { gcPauseMs += parseFloat(gcM[1]); }
    var ttspM = src.match(/Reaching safepoint:\s*(\d+(?:\.\d+)?)\s*ms/i);
    if (ttspM) { gcPauseMs += parseFloat(ttspM[1]); }
    if (gcPauseMs >= 15) {
      findings.push({
        rule_id: "CORR-002", severity: "critical", frame: "JVM:GC+Safepoint", domain: "JFR-CORR",
        message: "STW GC / Safepoint TTSP pause (" + gcPauseMs.toFixed(1) + " ms) overlaps tick spike and masks Java CPU frames.",
        remediation: "Enable Generational ZGC (-XX:+UseZGC -XX:+ZGenerational) and diagnose TTSP with -XX:+SafepointTimeout."
      });
    }
    if (low.indexOf("jdk.javamonitorenter") >= 0) {
      findings.push({
        rule_id: "CORR-003", severity: "critical", frame: "jdk.JavaMonitorEnter", domain: "JFR-CORR",
        message: "Cross-thread monitor lock convoy stalls Region/Server tick thread behind background worker.",
        remediation: "Replace coarse synchronized caches with ConcurrentHashMap or Folia RegionizedData."
      });
    }
    if ((low.indexOf("jdk.fileforce") >= 0 || low.indexOf("jdk.socketread") >= 0) && low.indexOf("waitingget") >= 0) {
      findings.push({
        rule_id: "CORR-004", severity: "critical", frame: "JFR:FileForce->waitingGet", domain: "JFR-CORR",
        message: "Background disk fsync / socket stall overlaps tick thread parked in CompletableFuture.waitingGet.",
        remediation: "Remove tick-thread future .join() barriers and disable synchronous region fsync."
      });
    }
    if (low.indexOf("jdk.virtualthreadpinned") >= 0) {
      findings.push({
        rule_id: "CORR-006", severity: "high", frame: "jdk.VirtualThreadPinned", domain: "JFR-CORR",
        message: "Virtual thread pinned carrier thread inside synchronized monitor or JNI call.",
        remediation: "Migrate I/O locks to ReentrantLock or run on JDK 25 JEP 491 unpinned monitors."
      });
    }
    var regLoads = [];
    src.split(/\r?\n/).forEach(function (ln) {
      var m = ln.match(/^(?:Folia )?Region Scheduler Thread #\d+;.+?\s+(\d+(?:\.\d+)?)$/i);
      if (m) { regLoads.push(parseFloat(m[1])); }
    });
    if (regLoads.length >= 2) {
      var sumR = regLoads.reduce(function (a, b) { return a + b; }, 0);
      var maxR = Math.max.apply(null, regLoads);
      if (sumR > 0 && (maxR / sumR) >= 0.65) {
        findings.push({
          rule_id: "CORR-007", severity: "high", frame: "FoliaRegionScheduler", domain: "JFR-CORR",
          message: "Hot Folia region consumes " + Math.round((maxR / sumR) * 100) + "% of regional tick weight across " + regLoads.length + " threads.",
          remediation: "Shard dense hubs and boss arenas > 32 chunks apart so Folia splits region ownership."
        });
      }
    }

    return {
      tool: "mc_profile_chunk_io_barriers+mc_correlate_spark_jfr_traces",
      status: findings.length ? "fail" : "pass",
      stw_pause_ms: Math.round(gcPauseMs * 10) / 10,
      pinned_ram_mb: pinnedRamMb,
      finding_count: findings.length,
      findings: findings
    };
  }

  function toSarif(report) {
    return {
      version: "2.1.0",
      runs: [
        {
          tool: {
            driver: {
              name: "minecraftkit",
              semanticVersion: "3.0.0",
              rules: report.findings.map(function (f) {
                return { id: f.rule_id, shortDescription: { text: f.message } };
              })
            }
          },
          results: report.findings.map(function (f) {
            return {
              ruleId: f.rule_id,
              level: f.severity === "critical" || f.severity === "high" ? "error" : "warning",
              message: { text: f.message },
              locations: [{ logicalLocations: [{ fullyQualifiedName: f.frame, kind: "function" }] }]
            };
          })
        }
      ]
    };
  }

  var mode = "spark";
  var showSarif = false;
  var lastReport = null;

  var tabSpark = document.getElementById("tab-spark");
  var tabFolia = document.getElementById("tab-folia");
  var tabProtoSql = document.getElementById("tab-protocol-sql");
  var tabChunkJfr = document.getElementById("tab-chunk-jfr");
  var tabBotOps = document.getElementById("tab-bot-ops");
  var tabPackCfg = document.getElementById("tab-pack-cfg");
  var tabMythicMmo = document.getElementById("tab-mythic-mmo");
  var tabSkriptWgEco = document.getElementById("tab-skript-wg-eco");
  var tabPluginSpigot = document.getElementById("tab-plugin-spigot");
  var tabProxyGeyser = document.getElementById("tab-proxy-geyser");
  var presetBox = document.getElementById("preset-buttons");
  var inputHeading = document.getElementById("input-heading");
  var inputSubtitle = document.getElementById("input-subtitle");
  var thresholdWrap = document.getElementById("threshold-wrap");
  var thresholdInput = document.getElementById("threshold-input");
  var domainWrap = document.getElementById("domain-wrap");
  var domainSelect = document.getElementById("domain-select");
  var traceInput = document.getElementById("trace-input");
  var runBtn = document.getElementById("run-audit-btn");
  var sarifBtn = document.getElementById("toggle-sarif-btn");
  var copyBtn = document.getElementById("copy-json-btn");
  var summaryLine = document.getElementById("summary-line");
  var metricsRow = document.getElementById("metrics-row");
  var findingsList = document.getElementById("findings-list");
  var jsonPreview = document.getElementById("json-preview");

  function clearNode(node) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
  }

  function renderMetrics(items) {
    clearNode(metricsRow);
    items.forEach(function (it) {
      var box = el("div", "metric-box");
      box.append(el("strong", "", it[0]), el("span", "", it[1]));
      metricsRow.append(box);
    });
  }

  function analyzeBotAndOps(rawText) {
    var text = String(rawText || "");
    var findings = [];
    if (/^\s*online-mode\s*=\s*false\b/mi.test(text) && !/server-ip\s*=\s*127\.0\.0\.1\b/mi.test(text)) {
      findings.push({
        rule_id: "PROXY-001",
        severity: "critical",
        frame: "server.properties::online-mode",
        message: "online-mode=false without loopback server-ip=127.0.0.1 allows direct UUID spoofing bypassing Velocity/BungeeCord.",
        remediation: "Bind backend servers strictly to server-ip=127.0.0.1 and firewall port 25565 on backend hosts."
      });
    }
    if (/^\s*enable-rcon\s*=\s*true\b/mi.test(text) && (/rcon\.password\s*=\s*(123456|admin|admin123|password|changeme)\b/mi.test(text) || !/rcon\.password\s*=\s*\S{12,}/mi.test(text))) {
      findings.push({
        rule_id: "OPS-RCON-001",
        severity: "high",
        frame: "server.properties::rcon.password",
        message: "Source RCON is enabled with a weak or short password (plaintext TCP protocol).",
        remediation: "Disable RCON or restrict to 127.0.0.1 / SSH tunnel with a 24+ char secret."
      });
    }
    if (/passwordHash:\s*(MD5|SHA1|SHA256)\b/i.test(text)) {
      findings.push({
        rule_id: "AUTH-001",
        severity: "high",
        frame: "AuthMe::passwordHash",
        message: "Weak AuthMe/nLogin password hash detected (fast unsalted/GPU-crackable digest).",
        remediation: "Switch AuthMe/nLogin passwordHash to ARGON2 or BCRYPT."
      });
    }
    if (/\/(?:login|l|register|reg)\s+(?!\[REDACTED|env:|\$\{)\S+/i.test(text)) {
      findings.push({
        rule_id: "BOT-SEC-001",
        severity: "critical",
        frame: "mckit-stages.yml::auto_auth",
        message: "Hardcoded plaintext password found inside bot stage command.",
        remediation: "Use action: auto_auth with password: env:MCKIT_BOT_PASS so secrets are never stored in YAML."
      });
    }
    var botCountMatch = text.match(/bot_count:\s*(\d+)/i);
    var bots = botCountMatch ? parseInt(botCountMatch[1], 10) : 1;
    var isDesktop = /desktop-full-client/i.test(text);
    var estRamMb = isDesktop ? bots * 2600 : bots * 42;
    if (isDesktop && bots > 2) {
      findings.push({
        rule_id: "BOT-OOM-001",
        severity: "high",
        frame: "bot-fleet::ram-budget",
        message: bots + " desktop Minecraft clients require ~" + (estRamMb / 1024).toFixed(1) + " GB RAM and hijack desktop focus.",
        remediation: "Switch to tier1-protocol (~42 MB/bot) or hybrid 1 Xvfb + N-1 protocol bots (saves >90% RAM)."
      });
    }
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "bot_ops",
      status: status,
      finding_count: findings.length,
      bots_planned: bots,
      estimated_ram_mb: estRamMb,
      screen_lock_free: !isDesktop,
      findings: findings
    };
  }

  function analyzePackAndConfig(rawText) {
    var text = String(rawText || "");
    var findings = [];
    if (/^\s*sync-chunk-writes\s*=\s*true\b/mi.test(text)) {
      findings.push({
        rule_id: "CFG-001",
        severity: "critical",
        frame: "server.properties::sync-chunk-writes",
        message: "sync-chunk-writes=true stalls tick threads on synchronous disk fsync.",
        remediation: "Set sync-chunk-writes=false to keep Moonrise chunk I/O asynchronous."
      });
    }
    var simM = text.match(/^\s*simulation-distance\s*[:=]\s*(\d+)/mi);
    if (simM && parseInt(simM[1], 10) > 8) {
      findings.push({
        rule_id: "CFG-002",
        severity: "high",
        frame: "server.properties::simulation-distance",
        message: "simulation-distance=" + simM[1] + " ticks excessive chunks per player.",
        remediation: "Lower simulation-distance to 6-8 and rely on view-distance for horizon visuals."
      });
    }
    var mobM = text.match(/^\s*monsters\s*[:=]\s*(\d+)/mi);
    if ((mobM && parseInt(mobM[1], 10) > 50) || /^\s*per-player-mob-spawns\s*[:=]\s*false\b/mi.test(text)) {
      findings.push({
        rule_id: "CFG-003",
        severity: "high",
        frame: "paper-world-defaults.yml::spawning",
        message: "Uncapped monsters or disabled per-player-mob-spawns creates mob-farm tick spikes.",
        remediation: "Enable per-player-mob-spawns: true and cap bukkit.yml monsters at 40-50."
      });
    }
    if (/treasure-maps-find-already-discovered\s*:\s*false/i.test(text)) {
      findings.push({
        rule_id: "CFG-004",
        severity: "high",
        frame: "paper-world-defaults.yml::treasure-maps",
        message: "Undiscovered treasure maps trigger multi-second synchronous chunk generation freezes.",
        remediation: "Set treasure-maps.find-already-discovered to true."
      });
    }
    if (/region-file-compression\s*=\s*(?:zlib|deflate)\b/i.test(text)) {
      findings.push({
        rule_id: "CFG-005",
        severity: "medium",
        frame: "server.properties::region-file-compression",
        message: "Legacy zlib/deflate chunk compression is slower than LZ4 on modern NVMe.",
        remediation: "Switch region-file-compression=lz4."
      });
    }
    var pfM = text.match(/"pack_format"\s*:\s*(\d+)/);
    if (pfM && parseInt(pfM[1], 10) < 46) {
      findings.push({
        rule_id: "PACK-001",
        severity: "high",
        frame: "pack.mcmeta::pack_format",
        message: "pack_format=" + pfM[1] + " predates Minecraft 1.21.4 (expected >= 46).",
        remediation: "Update pack_format to 46 (1.21.4) or 88 (26.2/26.3) and declare supported_formats."
      });
    }
    if (/"overrides"\s*:\s*\[/.test(text)) {
      findings.push({
        rule_id: "PACK-005",
        severity: "medium",
        frame: "models/item/*.json::overrides",
        message: "Legacy models/item overrides array is ignored in Minecraft 1.21.4+.",
        remediation: "Migrate to assets/<namespace>/items/<id>.json using minecraft:range_dispatch or minecraft:select."
      });
    }
    var score = Math.max(0, 100 - findings.reduce(function (acc, f) {
      return acc + (f.severity === "critical" ? 30 : (f.severity === "high" ? 15 : 8));
    }, 0));
    var grade = score >= 90 ? "A" : (score >= 78 ? "B" : (score >= 62 ? "C" : (score >= 45 ? "D" : "F")));
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "pack_cfg",
      status: status,
      grade: grade,
      score: score,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzeMythicMmo(raw) {
    var findings = [];
    var timers = raw.match(/~onTimer\s*:\s*([0-4])\b/gi);
    if (timers && timers.length) {
      findings.push({
        rule_id: "RPG-001",
        severity: "critical",
        message: "Sub-5-tick ~onTimer trigger (" + timers[0] + ") risks main-thread & Folia region TPS collapse.",
        remediation: "Raise ~onTimer to >= 10-20 ticks (0.5s-1s) or gate behind cooldowns."
      });
    }
    var radM = raw.match(/(?:@(?:EIR|EntitiesInRadius|PIR|PlayersInRadius)\{[^}]*\br(?:adius)?\s*=\s*(\d+)|\bradius\s*[:=]\s*(\d+))/i);
    if (radM && Number(radM[1] || radM[2]) > 64) {
      findings.push({
        rule_id: "RPG-002",
        severity: "critical",
        message: "Oversized entity targeter radius (" + (radM[1] || radM[2]) + " blocks > 64) causes chunk-scan lag bombs.",
        remediation: "Cap @EIR / @PIR / radius to <= 32-48 blocks with target limiters."
      });
    }
    var partM = raw.match(/(?:particles?|effect:particles?)\{[^}]*\b(?:a|amount|count|points)\s*=\s*(\d+)/i);
    if (partM && Number(partM[1]) > 500) {
      findings.push({
        rule_id: "RPG-003",
        severity: "high",
        message: "Excessive particle burst (" + partM[1] + " > 500) risks Netty bandwidth spikes and Geyser kicks.",
        remediation: "Keep particle counts <= 120 per burst."
      });
    }
    if (/(?:attack-damage|damage|max-health)\s*[:=]\s*(?:-\d+|\d{5,})/i.test(raw) || /(?:cooldown|mana|stamina|price|cost)\s*[:=]\s*-\d+/i.test(raw)) {
      findings.push({
        rule_id: "RPG-004",
        severity: "critical",
        message: "Combat or economy stat exploit detected (negative cost/mana or >10,000 damage).",
        remediation: "Clamp damage/health to server tier bounds and enforce strictly non-negative costs."
      });
    }
    if (/~on(?:Swing|Attack|Use|RightClick|Interact)\b/i.test(raw) && !/\bcooldown\s*[:=]\s*[1-9]\d*/i.test(raw)) {
      findings.push({
        rule_id: "RPG-005",
        severity: "medium",
        message: "Spam-able interaction trigger (~onAttack/~onUse/~onSwing) lacks a positive Cooldown.",
        remediation: "Add Cooldown: 2 (or skill-level cooldown) to block auto-clicker skill spam."
      });
    }
    var score = Math.max(0, 100 - findings.reduce(function (acc, f) {
      return acc + (f.severity === "critical" ? 30 : (f.severity === "high" ? 15 : 8));
    }, 0));
    var grade = score >= 90 ? "A" : (score >= 78 ? "B" : (score >= 62 ? "C" : (score >= 45 ? "D" : "F")));
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "mythic_mmo",
      status: status,
      grade: grade,
      score: score,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzeSkriptWgEco(raw) {
    var findings = [];
    if (/^\s*every\s+[1-4]\s+ticks?\s*:/mi.test(raw)) {
      findings.push({
        rule_id: "SK-001", severity: "critical", frame: "Skript::every-tick",
        message: "Sub-5-tick Skript periodic loop executes on the main tick thread and collapses TPS.",
        remediation: "Raise interval to 'every 2 seconds:' or switch to event-driven triggers."
      });
    }
    if (/loop\s+all\s+(?:entities|blocks)\b/i.test(raw)) {
      findings.push({
        rule_id: "SK-002", severity: "critical", frame: "Skript::loop-all",
        message: "Unbounded 'loop all entities/blocks' scans every loaded chunk in every world.",
        remediation: "Scope to 'loop all entities in radius 16 around player:'."
      });
    }
    if (/execute\s+console\s+command\s+"[^"]*%(?:arg-\d+|message|chat)%/i.test(raw)) {
      findings.push({
        rule_id: "SK-003", severity: "critical", frame: "Skript::console-inject",
        message: "Unsanitized player input interpolated into 'execute console command' allows privilege escalation.",
        remediation: "Use native Skript effects or strictly validate against an alphanumeric whitelist."
      });
    }
    if (/(?:spawn|hub|lobby)[\s\S]{0,160}?\b(?:tnt|creeper-explosion|fire-spread)\s*:\s*allow\b/i.test(raw)) {
      findings.push({
        rule_id: "WG-001", severity: "critical", frame: "WorldGuard::spawn-grief",
        message: "Protected spawn/hub region allows TNT, creeper explosion, or fire-spread.",
        remediation: "Set tnt: deny, creeper-explosion: deny, and fire-spread: deny on spawn regions."
      });
    }
    if (/(?:spawn|hub|lobby)[\s\S]{0,160}?\bpassthrough\s*:\s*allow\b/i.test(raw)) {
      findings.push({
        rule_id: "WG-002", severity: "high", frame: "WorldGuard::passthrough",
        message: "passthrough: allow bypasses default WorldGuard build protection on a hub/spawn region.",
        remediation: "Remove passthrough: allow or set build: deny explicitly."
      });
    }
    var buyM = raw.match(/\bbuy(?:-price)?\s*:\s*(-?\d+(?:\.\d+)?)/i);
    var sellM = raw.match(/\bsell(?:-price)?\s*:\s*(-?\d+(?:\.\d+)?)/i);
    if (buyM && sellM && parseFloat(sellM[1]) > parseFloat(buyM[1]) && parseFloat(buyM[1]) > 0) {
      findings.push({
        rule_id: "ECO-001", severity: "critical", frame: "ShopGUI::buy-sell-dupe",
        message: "Infinite money exploit: sell price (" + sellM[1] + ") exceeds buy price (" + buyM[1] + ").",
        remediation: "Enforce sell price <= 50-70% of buy price across all shop items."
      });
    }
    var startBalM = raw.match(/\bstarting-balance\s*:\s*(\d+)/i);
    if (startBalM && parseInt(startBalM[1], 10) >= 1000000) {
      findings.push({
        rule_id: "ECO-003", severity: "high", frame: "Economy::starting-balance",
        message: "Excessive starting-balance (" + startBalM[1] + ") fuels alt-account inflation farming.",
        remediation: "Cap starting-balance <= 5,000 and add transaction tax sinks."
      });
    }
    var score = Math.max(0, 100 - findings.reduce(function (acc, f) {
      return acc + (f.severity === "critical" ? 28 : (f.severity === "high" ? 15 : 8));
    }, 0));
    var grade = score >= 90 ? "A" : (score >= 78 ? "B" : (score >= 62 ? "C" : (score >= 45 ? "D" : "F")));
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "skript_wg_eco",
      status: status,
      grade: grade,
      score: score,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzePluginSpigot(raw) {
    var findings = [];
    if (/^\s*bungeecord\s*:\s*true\b/mi.test(raw)) {
      findings.push({
        rule_id: "SPG-001", severity: "critical", frame: "spigot.yml::bungeecord",
        message: "Legacy spigot.yml bungeecord: true enables spoofable legacy IP forwarding.",
        remediation: "Migrate to Velocity modern forwarding in paper-global.yml and set bungeecord: false."
      });
    }
    var monM = raw.match(/^\s*monsters\s*:\s*(\d+)/mi);
    if (monM && parseInt(monM[1], 10) > 70) {
      findings.push({
        rule_id: "SPG-002", severity: "high", frame: "bukkit.yml::spawn-limits",
        message: "Excessive monster spawn limit (" + monM[1] + " > 70) spikes mob AI tick cost.",
        remediation: "Cap bukkit.yml spawn-limits.monsters at 40-55 and tune entity-activation-range."
      });
    }
    if (/^\s*main\s*:/mi.test(raw) && !/^\s*api-version\s*:/mi.test(raw)) {
      findings.push({
        rule_id: "PLG-001", severity: "critical", frame: "plugin.yml::api-version",
        message: "Missing api-version forces expensive legacy Material/NMS bytecode rewriting on every boot.",
        remediation: "Declare api-version: '1.21.4' (or your target Paper API version)."
      });
    }
    if (/^\s*main\s*:/mi.test(raw) && !/^\s*folia-supported\s*:\s*true\b/mi.test(raw)) {
      findings.push({
        rule_id: "PLG-002", severity: "medium", frame: "plugin.yml::folia-supported",
        message: "Plugin manifest does not declare folia-supported: true and will be refused by Folia servers.",
        remediation: "Migrate schedulers to RegionScheduler/EntityScheduler and add folia-supported: true."
      });
    }
    if (/^\s*load\s*:\s*STARTUP\b/mi.test(raw)) {
      findings.push({
        rule_id: "PLG-003", severity: "high", frame: "plugin.yml::load",
        message: "load: STARTUP runs before worlds exist and commonly causes NullPointerException on world lookups.",
        remediation: "Use default POSTWORLD load phase unless registering a custom ChunkGenerator."
      });
    }
    if (/default\s*:\s*true\b/i.test(raw) && /(?:admin|\*)/i.test(raw)) {
      findings.push({
        rule_id: "PLG-004", severity: "critical", frame: "plugin.yml::permissions",
        message: "Wildcard or admin permission defaults to true (grants elevated access to every player!).",
        remediation: "Set default: op or default: false on all admin/wildcard permission nodes."
      });
    }
    var score = Math.max(0, 100 - findings.reduce(function (acc, f) {
      return acc + (f.severity === "critical" ? 28 : (f.severity === "high" ? 15 : 8));
    }, 0));
    var grade = score >= 90 ? "A" : (score >= 78 ? "B" : (score >= 62 ? "C" : (score >= 45 ? "D" : "F")));
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "plugin_spigot",
      status: status,
      grade: grade,
      score: score,
      finding_count: findings.length,
      findings: findings
    };
  }

  function analyzeProxyGeyserNet(raw) {
    var findings = [];
    if (/player-info-forwarding-mode\s*=\s*["']?(?:legacy|none)["']?/i.test(raw)) {
      findings.push({
        rule_id: "VEL-001", severity: "critical", frame: "velocity.toml::player-info-forwarding-mode",
        message: "Velocity uses legacy/none forwarding instead of modern HMAC-SHA256 forwarding.",
        remediation: "Set player-info-forwarding-mode = \"modern\" and enable Paper proxies.velocity.enabled."
      });
    }
    if (/^\s*online-mode\s*=\s*false\b/mi.test(raw)) {
      findings.push({
        rule_id: "VEL-002", severity: "critical", frame: "velocity.toml::online-mode",
        message: "Proxy online-mode=false allows cracked UUID spoofing unless strictly fronted by AuthMeVelocity/LimboAuth.",
        remediation: "Set online-mode = true or verify isolated LimboAuth + firewall backend ports."
      });
    }
    if (/forwarding-secret\s*=\s*["'](?:changeme|secret|password|123456|default)?["']/i.test(raw)) {
      findings.push({
        rule_id: "VEL-003", severity: "high", frame: "velocity.toml::forwarding-secret",
        message: "Weak or placeholder Velocity forwarding secret detected.",
        remediation: "Use forwarding-secret-file with a 32+ byte random secret kept outside version control."
      });
    }
    if (/auth-type\s*:\s*offline\b/i.test(raw)) {
      findings.push({
        rule_id: "GEY-001", severity: "critical", frame: "geyser/config.yml::auth-type",
        message: "Geyser auth-type: offline disables Floodgate cryptographic identity verification for Bedrock players.",
        remediation: "Switch remote.auth-type to floodgate (recommended) or online."
      });
    }
    var mtuM = raw.match(/^\s*mtu\s*:\s*(\d+)/mi);
    if (mtuM && parseInt(mtuM[1], 10) > 1400) {
      findings.push({
        rule_id: "GEY-002", severity: "medium", frame: "geyser/config.yml::mtu",
        message: "Bedrock RakNet MTU (" + mtuM[1] + " > 1400) causes UDP fragmentation and mobile disconnects.",
        remediation: "Set mtu: 1400 in Geyser config.yml."
      });
    }
    if (/exempt-ops\s*:\s*true\b/i.test(raw) || /^\s*verbose\s*:\s*true\b/mi.test(raw)) {
      findings.push({
        rule_id: "AC-001", severity: "high", frame: "anticheat::config.yml",
        message: "AntiCheat exempt-ops: true or verbose: true weakens compromised-account protection or floods I/O.",
        remediation: "Disable verbose logging in production and gate exemptions with explicit permission nodes."
      });
    }
    var score = Math.max(0, 100 - findings.reduce(function (acc, f) {
      return acc + (f.severity === "critical" ? 28 : (f.severity === "high" ? 15 : 8));
    }, 0));
    var grade = score >= 90 ? "A" : (score >= 78 ? "B" : (score >= 62 ? "C" : (score >= 45 ? "D" : "F")));
    var status = findings.some(function (f) { return f.severity === "critical" || f.severity === "high"; }) ? "fail" : (findings.length ? "warn" : "pass");
    return {
      mode: "proxy_geyser_net",
      status: status,
      grade: grade,
      score: score,
      finding_count: findings.length,
      findings: findings
    };
  }

  function renderReport(report) {
    lastReport = report;
    summaryLine.textContent = "Status: " + report.status.toUpperCase() + " | " + report.finding_count + " finding(s)";
    if (mode === "spark") {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        [report.profile_format, "Format"],
        [report.finding_count, "Hotspots"],
        [report.benign_idle_workers, "Idle Async Parked"]
      ]);
    } else if (mode === "folia") {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        [report.threads_analyzed, "Threads"],
        [report.domains_detected.join(", ") || "NONE", "Domains"],
        [report.finding_count, "Violations"]
      ]);
    } else if (mode === "chunk_jfr") {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        [report.stw_pause_ms + " ms", "GC + TTSP Overlap"],
        [report.pinned_ram_mb + " MiB", "Pinned Ticket RAM"],
        [report.finding_count, "Violations"]
      ]);
    } else if (mode === "bot_ops") {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        [report.bots_planned + " bot(s)", "Fleet Size"],
        [report.estimated_ram_mb + " MB", "Est. RAM"],
        [report.screen_lock_free ? "ZERO LOCK" : "FOCUS LOCK", "Desktop Impact"]
      ]);
    } else if (mode === "pack_cfg" || mode === "mythic_mmo" || mode === "skript_wg_eco" || mode === "plugin_spigot" || mode === "proxy_geyser_net") {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        ["Grade " + report.grade, "Health Grade"],
        [report.score + "/100", "Safety Score"],
        [report.finding_count, "Findings"]
      ]);
    } else {
      renderMetrics([
        [report.status.toUpperCase(), "Verdict"],
        [report.max_wire_bytes + " B", "Worst-Case Wire"],
        [report.wire_cap_bytes + " B", "Serverbound Cap"],
        [report.finding_count, "Violations"]
      ]);
    }

    clearNode(findingsList);
    if (report.findings.length === 0) {
      var okCard = el("article", "finding-card sev-pass");
      okCard.append(
        el("div", "finding-head", "PASS :: Zero hazards above threshold"),
        el("p", "finding-msg", "All sampled frames and Folia scheduler domain boundaries satisfy thread-affinity and tick-budget invariants.")
      );
      findingsList.append(okCard);
    } else {
      report.findings.forEach(function (f) {
        var card = el("article", "finding-card sev-" + f.severity);
        var head = el("div", "finding-head");
        head.append(
          el("span", "finding-badge", f.rule_id + " [" + f.severity.toUpperCase() + "]" + (f.plugin ? " :: " + f.plugin : "")),
          el("span", "", f.domain ? ("Domain: " + f.domain) : (f.pct !== undefined ? (f.pct + "%") : ""))
        );
        card.append(head, el("p", "finding-msg", f.message), el("p", "finding-fix", "Fix: " + f.remediation));
        findingsList.append(card);
      });
    }

    jsonPreview.textContent = JSON.stringify(showSarif ? toSarif(report) : report, null, 2);
    jsonPreview.hidden = !showSarif;
  }

  function runAudit() {
    if (mode === "spark") {
      var thr = parseFloat(thresholdInput.value) || 5.0;
      renderReport(analyzeSpark(traceInput.value, thr));
    } else if (mode === "folia") {
      renderReport(analyzeFolia(traceInput.value, domainSelect.value));
    } else if (mode === "chunk_jfr") {
      renderReport(analyzeChunkAndJfr(traceInput.value));
    } else if (mode === "bot_ops") {
      renderReport(analyzeBotAndOps(traceInput.value));
    } else if (mode === "pack_cfg") {
      renderReport(analyzePackAndConfig(traceInput.value));
    } else if (mode === "mythic_mmo") {
      renderReport(analyzeMythicMmo(traceInput.value));
    } else if (mode === "skript_wg_eco") {
      renderReport(analyzeSkriptWgEco(traceInput.value));
    } else if (mode === "plugin_spigot") {
      renderReport(analyzePluginSpigot(traceInput.value));
    } else if (mode === "proxy_geyser_net") {
      renderReport(analyzeProxyGeyserNet(traceInput.value));
    } else {
      renderReport(analyzeProtocolAndSql(traceInput.value));
    }
  }

  function renderPresets() {
    clearNode(presetBox);
    PRESETS[mode].forEach(function (p) {
      var b = el("button", "preset-btn", p.label);
      b.type = "button";
      b.addEventListener("click", function () {
        traceInput.value = p.text;
        if (p.threshold) { thresholdInput.value = String(p.threshold); }
        if (p.domain) { domainSelect.value = p.domain; }
        runAudit();
      });
      presetBox.append(b);
    });
  }

  function switchMode(nextMode) {
    mode = nextMode;
    var isSpark = mode === "spark";
    var isFolia = mode === "folia";
    var isProtoSql = mode === "protocol_sql";
    var isChunkJfr = mode === "chunk_jfr";
    var isBotOps = mode === "bot_ops";
    var isPackCfg = mode === "pack_cfg";
    var isMythicMmo = mode === "mythic_mmo";
    var isSkriptWgEco = mode === "skript_wg_eco";
    var isPluginSpigot = mode === "plugin_spigot";
    var isProxyGeyser = mode === "proxy_geyser_net";
    tabSpark.classList.toggle("is-active", isSpark);
    tabSpark.setAttribute("aria-selected", String(isSpark));
    tabFolia.classList.toggle("is-active", isFolia);
    tabFolia.setAttribute("aria-selected", String(isFolia));
    if (tabProtoSql) {
      tabProtoSql.classList.toggle("is-active", isProtoSql);
      tabProtoSql.setAttribute("aria-selected", String(isProtoSql));
    }
    if (tabChunkJfr) {
      tabChunkJfr.classList.toggle("is-active", isChunkJfr);
      tabChunkJfr.setAttribute("aria-selected", String(isChunkJfr));
    }
    if (tabBotOps) {
      tabBotOps.classList.toggle("is-active", isBotOps);
      tabBotOps.setAttribute("aria-selected", String(isBotOps));
    }
    if (tabPackCfg) {
      tabPackCfg.classList.toggle("is-active", isPackCfg);
      tabPackCfg.setAttribute("aria-selected", String(isPackCfg));
    }
    if (tabMythicMmo) {
      tabMythicMmo.classList.toggle("is-active", isMythicMmo);
      tabMythicMmo.setAttribute("aria-selected", String(isMythicMmo));
    }
    if (tabSkriptWgEco) {
      tabSkriptWgEco.classList.toggle("is-active", isSkriptWgEco);
      tabSkriptWgEco.setAttribute("aria-selected", String(isSkriptWgEco));
    }
    if (tabPluginSpigot) {
      tabPluginSpigot.classList.toggle("is-active", isPluginSpigot);
      tabPluginSpigot.setAttribute("aria-selected", String(isPluginSpigot));
    }
    if (tabProxyGeyser) {
      tabProxyGeyser.classList.toggle("is-active", isProxyGeyser);
      tabProxyGeyser.setAttribute("aria-selected", String(isProxyGeyser));
    }
    thresholdWrap.hidden = !isSpark;
    domainWrap.hidden = !isFolia;
    if (isSpark) {
      inputHeading.textContent = "Spark Collapsed Stack or Call-Tree Input";
      inputSubtitle.textContent = "Zero-upload browser analysis. Distinguishes sync tick bottlenecks and HikariCP starvation from idle worker parking.";
    } else if (isFolia) {
      inputHeading.textContent = "Folia Stack Trace or Multi-Thread Dump";
      inputSubtitle.textContent = "Verifies Folia 4-domain state ownership across REGION, ENTITY, GLOBAL, ASYNC, and NETTY threads.";
    } else if (isChunkJfr) {
      inputHeading.textContent = "Moonrise Chunk I/O Pipeline or Spark + JFR + GC Timeline";
      inputSubtitle.textContent = "Profiles Moonrise chunk barriers and ticket RAM (CHUNK-IO-001..008) and correlates JFR lock/I/O/GC pauses (CORR-001..007).";
    } else if (isBotOps) {
      inputHeading.textContent = "Bot Stage YAML, AuthMe & Proxy Security Pre-Flight";
      inputSubtitle.textContent = "Audits hardcoded bot passwords, online-mode/proxy bypasses, weak RCON/AuthMe hashes, and desktop RAM OOM hazards completely offline.";
    } else if (isPackCfg) {
      inputHeading.textContent = "Paper/Purpur/Folia Anti-Lag Config & 1.21.4+ Resource Pack Linter";
      inputSubtitle.textContent = "Catches sync-chunk-writes, mob-farm/hopper lag, treasure-map freezes, and legacy pack_format/overrides offline (CFG-001..005, PACK-001..005).";
    } else if (isMythicMmo) {
      inputHeading.textContent = "MythicMobs Skill/Mob & MMOItems/Crucible YAML Linter";
      inputSubtitle.textContent = "Detects sub-5-tick ~onTimer loops, >64-block @EIR chunk scans, >500 particle floods, negative costs, and missing cooldowns offline (RPG-001..005).";
    } else if (isSkriptWgEco) {
      inputHeading.textContent = "Skript, WorldGuard Regions & Economy Shop Anti-Dupe Linter";
      inputSubtitle.textContent = "Catches 1-tick Skript loops, console command injection, unprotected spawn TNT/passthrough flags, and buy < sell infinite money exploits offline.";
    } else if (isPluginSpigot) {
      inputHeading.textContent = "Bukkit/Spigot YAML & plugin.yml / paper-plugin.yml Pre-Boot Linter";
      inputSubtitle.textContent = "Catches legacy bungeecord:true spoofing, high spawn-limits, missing api-version, load:STARTUP hazards, and default:true admin wildcards offline.";
    } else if (isProxyGeyser) {
      inputHeading.textContent = "Velocity Proxy, GeyserMC/Floodgate & AntiCheat Network Linter";
      inputSubtitle.textContent = "Catches legacy proxy forwarding, online-mode bypasses, placeholder forwarding secrets, offline Geyser auth, MTU fragmentation, and verbose AntiCheat configs offline.";
    } else {
      inputHeading.textContent = "Netty StreamCodec or HikariCP / SQL Persistence Snippet";
      inputSubtitle.textContent = "Computes worst-case LEB128/UTF-8 wire-byte budgets (NETTY-001..008) and audits sync JDBC, resource leaks, and Folia callbacks (SQL-001..007).";
    }
    renderPresets();
    traceInput.value = PRESETS[mode][0].text;
    runAudit();
  }

  tabSpark.addEventListener("click", function () { switchMode("spark"); });
  tabFolia.addEventListener("click", function () { switchMode("folia"); });
  if (tabProtoSql) {
    tabProtoSql.addEventListener("click", function () { switchMode("protocol_sql"); });
  }
  if (tabChunkJfr) {
    tabChunkJfr.addEventListener("click", function () { switchMode("chunk_jfr"); });
  }
  if (tabBotOps) {
    tabBotOps.addEventListener("click", function () { switchMode("bot_ops"); });
  }
  if (tabPackCfg) {
    tabPackCfg.addEventListener("click", function () { switchMode("pack_cfg"); });
  }
  if (tabMythicMmo) {
    tabMythicMmo.addEventListener("click", function () { switchMode("mythic_mmo"); });
  }
  if (tabSkriptWgEco) {
    tabSkriptWgEco.addEventListener("click", function () { switchMode("skript_wg_eco"); });
  }
  if (tabPluginSpigot) {
    tabPluginSpigot.addEventListener("click", function () { switchMode("plugin_spigot"); });
  }
  if (tabProxyGeyser) {
    tabProxyGeyser.addEventListener("click", function () { switchMode("proxy_geyser_net"); });
  }
  runBtn.addEventListener("click", runAudit);
  sarifBtn.addEventListener("click", function () {
    showSarif = !showSarif;
    sarifBtn.textContent = showSarif ? "Hide SARIF v2.1.0" : "View SARIF v2.1.0";
    if (lastReport) { renderReport(lastReport); }
  });
  copyBtn.addEventListener("click", function () {
    if (!lastReport || !navigator.clipboard) { return; }
    var payload = JSON.stringify(showSarif ? toSarif(lastReport) : lastReport, null, 2);
    navigator.clipboard.writeText(payload);
    copyBtn.textContent = "Copied";
    window.setTimeout(function () { copyBtn.textContent = "Copy JSON"; }, 1200);
  });

  switchMode("spark");
}());
