(function bootstrapMinecraftRPGKit(global) {
  "use strict";

  const kit = global.MinecraftRPGKit = global.MinecraftRPGKit || {};
  const registrationBuffer = new Map();
  const registrationWaiters = new Map();

  function pluginKey(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  kit.registerPlugin = function registerPlugin(payload) {
    if (!payload || !Array.isArray(payload.classes)) {
      return false;
    }

    const key = pluginKey(payload.name || payload.plugin || payload.jar);
    if (!key) {
      return false;
    }

    const waiter = registrationWaiters.get(key);
    if (waiter) {
      registrationWaiters.delete(key);
      waiter.resolve(payload);
    } else {
      registrationBuffer.set(key, payload);
    }

    return true;
  };

  const numberFormatter = new Intl.NumberFormat("en-US");
  const KIND_ORDER = ["class", "interface", "enum", "annotation", "record", "constructor", "method", "field"];
  const RUNE_CODES = {
    coretools: "[CT]",
    mmocore: "[MC]",
    mmoinventory: "[IV]",
    mmoitems: "[MI]",
    mmoprofiles: "[MP]",
    modelengine: "[ME]",
    mythiccrucible: "[CR]",
    mythicdungeons: "[DG]",
    mythicenchants: "[EN]",
    mythicrpg: "[RPG]"
  };

  const PLUGIN_CONTEXT = {
    coretools: {
      layer: "Automation and utility",
      role: "Hosts the configurable script context, stations, variables, economy, shops, auction, wardrobe, and shared data services.",
      relations: ["mmoitems", "mmoprofiles"],
      architecture: "Configured events enter a mutable Context, pass through conditions and targeters, then mechanics apply durable RPG side effects.",
      features: ["Script mechanics and conditions", "Crafting stations", "Variables and profile data", "Shops, vaults, and auction", "Multi-provider item resolution", "Private drops and wardrobe"]
    },
    mmocore: {
      layer: "Character progression",
      role: "Owns classes, skills, attributes, professions, quests, social modules, resources, skill trees, and experience rules.",
      relations: ["mmoitems", "mmoprofiles"],
      architecture: "Experience sources update the PlayerData aggregate, which refreshes class, profession, skill-tree, resource, trigger, and UI state.",
      features: ["Classes and subclasses", "Skills and casting", "Attributes and resources", "Professions and experience", "Parties, guilds, and quests", "Skill trees and waypoints"]
    },
    mmoinventory: {
      layer: "Equipment layout",
      role: "Defines custom inventories, typed slots, placement restrictions, player inventory persistence, and equipment interaction events.",
      relations: ["mmoitems"],
      architecture: "Configured slot layouts resolve into compact profile data or a live Bukkit inventory, then update events notify equipment consumers.",
      features: ["Custom inventory layouts", "Typed equipment slots", "Slot restrictions", "Vanilla and Elytra data", "Equip and use events", "Legacy RPGInventory bridge"]
    },
    mmoitems: {
      layer: "Item system",
      role: "Builds typed RPG items from templates, stats, tiers, modifiers, crafting recipes, upgrades, gems, sets, drops, and blocks.",
      relations: ["mmocore", "mmoinventory", "mmoprofiles", "mythiccrucible"],
      architecture: "Types and templates feed an item builder, stat formulas produce data, and ItemStackBuilder writes the final tags, lore, and effects.",
      features: ["Item types and templates", "Extensible item stats", "Tiers, sets, and modifiers", "Crafting station grammar", "Gems, upgrades, and durability", "Equipment effect resolution"]
    },
    mmoprofiles: {
      layer: "Character sessions",
      role: "Coordinates multiple character profiles, vanilla player-state snapshots, addon data modules, placeholders, and proxy handoff.",
      relations: ["coretools", "mmocore", "mmoitems"],
      architecture: "A profile selection opens a pending barrier. Every registered data module loads and validates before the player snapshot is applied.",
      features: ["Multiple character profiles", "Player-state snapshots", "Profile data modules", "Lifecycle events", "Profile placeholders", "Velocity proxy handoff"]
    },
    modelengine: {
      layer: "Model and rendering",
      role: "Maps entities to active models, bones, animation handlers, behaviors, hitboxes, mounts, VFX, culling, and viewer-specific rendering.",
      relations: ["mmoitems", "mythicdungeons", "mythicrpg"],
      architecture: "A modeled entity owns active models. Registries resolve blueprints and behaviors while phased tickers drive animation, interaction, and rendering.",
      features: ["Active model graphs", "Bone behaviors", "Animation state machines", "Dynamic hitboxes", "Mount controllers", "Viewer-aware VFX and LOD"]
    },
    mythiccrucible: {
      layer: "Mythic item runtime",
      role: "Connects Mythic mechanics to custom items, equipment actions, recipes, loot behavior, and item-focused addon hooks.",
      relations: ["mmoitems", "mythicrpg"],
      architecture: "Item definitions and registered mechanics enter Mythic execution paths, then Bukkit item events expose their runtime effects.",
      features: ["Mythic item definitions", "Equipment mechanics", "Recipe hooks", "Loot integration", "Item event actions", "Custom content registries"]
    },
    mythicdungeons: {
      layer: "Encounter orchestration",
      role: "Coordinates dungeon instances, rooms, objectives, checkpoints, parties, rewards, and scripted encounter state.",
      relations: ["modelengine", "mythicrpg"],
      architecture: "Dungeon sessions move parties through configured rooms and objectives while instance state controls encounter activation, completion, and cleanup.",
      features: ["Dungeon instances", "Rooms and objectives", "Party sessions", "Checkpoints", "Encounter scripting", "Reward and completion flow"]
    },
    mythicenchants: {
      layer: "Enchant mechanics",
      role: "Defines custom enchant effects, triggers, conditions, item application rules, and Mythic-aware equipment behavior.",
      relations: ["mmoitems", "mythicrpg"],
      architecture: "Registered enchant definitions bind item metadata to event triggers, then conditions gate mechanics when equipped or activated.",
      features: ["Custom enchant definitions", "Event triggers", "Mechanic conditions", "Item application rules", "Equipment effects", "Mythic integration"]
    },
    mythicrpg: {
      layer: "Mythic RPG framework",
      role: "Provides RPG-oriented Mythic abstractions for player progression, combat content, integrations, and reusable gameplay components.",
      relations: ["modelengine", "mythiccrucible", "mythicdungeons", "mythicenchants"],
      architecture: "Registered RPG components connect player state and Mythic execution, with adapters linking item, dungeon, enchant, and model systems.",
      features: ["RPG component registries", "Player state hooks", "Combat integrations", "Mythic mechanics", "Content adapters", "Cross-plugin extension points"]
    }
  };

  const ARCHITECTURE_FLOW = [
    { title: "Profile boundary", body: "MMOProfiles coordinates vanilla state and waits for addon-owned profile modules before opening the character session.", meta: "Session ownership" },
    { title: "Progression graph", body: "MMOCore turns experience sources into class, profession, resource, skill, quest, and social state updates.", meta: "PlayerData aggregate" },
    { title: "Item pipeline", body: "MMOItems and MythicCrucible resolve item definitions, formulas, modifiers, crafting rules, tags, and lifecycle events.", meta: "Template to ItemStack" },
    { title: "Equipment boundary", body: "MMOInventory supplies typed slots while item systems calculate derived abilities, effects, permissions, and set bonuses.", meta: "Buffered resolution" },
    { title: "Encounter runtime", body: "MythicDungeons and MythicRPG coordinate rooms, objectives, parties, mechanics, rewards, and cleanup.", meta: "Instance state" },
    { title: "Render surface", body: "ModelEngine maps encounter state to models, bones, animation, hitboxes, mounts, VFX, visibility, and LOD.", meta: "Viewer output" }
  ];

  const ADDON_IDEAS = [
    { title: "Adaptive Loot Director", body: "Tune encounter drops from party risk, recent failures, and gear saturation while keeping a visible pity budget.", meta: "MMOCore + MMOItems" },
    { title: "Profile-bound Seasonal Loadouts", body: "Persist a seasonal relic board per character, then migrate or lock slots when the season changes.", meta: "MMOProfiles + MMOInventory" },
    { title: "Crafting Research Tree", body: "Gate recipe branches with profession research nodes and award discovery experience for first-time formulas.", meta: "MMOCore + MMOItems" },
    { title: "Party Synergy Relics", body: "Activate relic bonuses from nearby party roles and recompute them only when roster or equipment state changes.", meta: "MMOCore + MMOInventory + MMOItems" },
    { title: "Cross-server Expedition Character", body: "Move a temporary character across a server cluster, then merge only approved rewards into its home profile.", meta: "MMOProfiles + progression data" },
    { title: "Item Provenance Ledger", body: "Record item build, station, reforge, and upgrade fingerprints to detect duplication and counterfeit high-value gear.", meta: "CoreTools + MMOItems" },
    { title: "Adaptive Boss Anatomy", body: "Bind sub-hitboxes to model bones so destroyed limbs change boss skills, movement, and animation choices.", meta: "ModelEngine + combat events" },
    { title: "Reactive Armor Break", body: "Detach visual armor bones and update item stats when durability crosses configured thresholds.", meta: "ModelEngine + MMOItems" },
    { title: "Spectral Replay Ghosts", body: "Record a dungeon run as transforms and replay it as a non-interactive model for route study.", meta: "ModelEngine + MythicDungeons" },
    { title: "Death Insurance Recovery Hunt", body: "Insure selected gear and turn uninsured losses into owner-bound recovery encounters instead of deletion.", meta: "MMOInventory + CoreTools" }
  ];

  const state = {
    manifest: null,
    pluginMeta: null,
    pluginData: null,
    index: [],
    filtered: [],
    page: 1,
    pageSize: 24,
    selectedId: null,
    view: "api",
    loadToken: 0,
    loadingSlug: null
  };

  const elements = {};

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function formatNumber(value) {
    return numberFormatter.format(Number(value) || 0);
  }

  function setStatus(message, mode) {
    elements.datasetState.textContent = message;
    elements.datasetState.className = "dataset-state";
    if (mode) {
      elements.datasetState.classList.add(`is-${mode}`);
    }
    elements.liveStatus.textContent = message;
  }

  function injectScript(source, label) {
    return new Promise(function scriptPromise(resolve, reject) {
      const script = document.createElement("script");
      script.src = source;
      script.async = true;
      script.dataset.localSource = label;
      script.onload = function handleLoad() {
        script.remove();
        resolve();
      };
      script.onerror = function handleError() {
        script.remove();
        reject(new Error(`Unable to load ${label}.`));
      };
      document.head.appendChild(script);
    });
  }

  function loadPluginShard(meta) {
    const key = pluginKey(meta.name);
    const buffered = registrationBuffer.get(key);
    if (buffered) {
      registrationBuffer.delete(key);
      return Promise.resolve(buffered);
    }

    return new Promise(function pluginPromise(resolve, reject) {
      registrationWaiters.set(key, { resolve, reject });
      const script = document.createElement("script");
      script.src = meta.file;
      script.async = true;
      script.dataset.pluginShard = meta.slug;

      script.onload = function handleShardLoad() {
        script.remove();
        Promise.resolve().then(function validateRegistration() {
          if (registrationWaiters.has(key)) {
            registrationWaiters.delete(key);
            reject(new Error(`${meta.name} did not register a valid API payload.`));
          }
        });
      };

      script.onerror = function handleShardError() {
        script.remove();
        registrationWaiters.delete(key);
        reject(new Error(`Unable to open ${meta.file}.`));
      };

      document.head.appendChild(script);
    });
  }

  function cacheElements() {
    elements.pluginRail = document.getElementById("plugin-rail");
    elements.railContext = document.getElementById("rail-context");
    elements.pluginSelect = document.getElementById("plugin-select");
    elements.activePluginName = document.getElementById("active-plugin-name");
    elements.datasetState = document.getElementById("dataset-state");
    elements.search = document.getElementById("api-search");
    elements.scope = document.getElementById("scope-filter");
    elements.origin = document.getElementById("origin-filter");
    elements.kind = document.getElementById("kind-filter");
    elements.package = document.getElementById("package-filter");
    elements.deprecated = document.getElementById("deprecated-filter");
    elements.filterForm = document.getElementById("api-filter-form");
    elements.resultCount = document.getElementById("result-count");
    elements.pageRange = document.getElementById("page-range");
    elements.symbolList = document.getElementById("symbol-list");
    elements.symbolDetail = document.getElementById("symbol-detail");
    elements.previous = document.getElementById("page-previous");
    elements.next = document.getElementById("page-next");
    elements.pageStatus = document.getElementById("page-status");
    elements.pageSize = document.getElementById("page-size");
    elements.liveStatus = document.getElementById("live-status");
    elements.footerDataset = document.getElementById("footer-dataset");
    elements.metricPlugins = document.getElementById("metric-plugins");
    elements.metricTypes = document.getElementById("metric-types");
    elements.metricMembers = document.getElementById("metric-members");
  }

  function bindEvents() {
    document.querySelectorAll("[data-view]").forEach(function bindView(button) {
      button.addEventListener("click", function changeView() {
        setView(button.dataset.view);
      });
    });

    elements.pluginSelect.addEventListener("change", function changePlugin() {
      selectPlugin(elements.pluginSelect.value);
    });

    elements.filterForm.addEventListener("submit", function preventFormSubmit(event) {
      event.preventDefault();
    });

    [elements.search, elements.scope, elements.origin, elements.kind, elements.package, elements.deprecated].forEach(function bindFilter(control) {
      control.addEventListener(control === elements.search ? "input" : "change", function updateFilter() {
        state.page = 1;
        applyFilters();
      });
    });

    elements.previous.addEventListener("click", function previousPage() {
      if (state.page > 1) {
        state.page -= 1;
        renderResults();
      }
    });

    elements.next.addEventListener("click", function nextPage() {
      const pageCount = Math.ceil(state.filtered.length / state.pageSize);
      if (state.page < pageCount) {
        state.page += 1;
        renderResults();
      }
    });

    elements.pageSize.addEventListener("change", function changePageSize() {
      state.pageSize = Number(elements.pageSize.value) || 24;
      state.page = 1;
      renderResults();
    });

    document.addEventListener("keydown", function keyboardShortcuts(event) {
      const target = event.target;
      const isTyping = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target.isContentEditable;

      if (event.key === "/" && !isTyping && !elements.search.disabled) {
        event.preventDefault();
        setView("api");
        elements.search.focus();
      }

      if (event.key === "Escape" && target === elements.search && elements.search.value) {
        elements.search.value = "";
        state.page = 1;
        applyFilters();
      }
    });
  }

  function setView(view) {
    if (!document.querySelector(`[data-view-panel="${view}"]`)) {
      return;
    }

    state.view = view;
    document.querySelectorAll("[data-view-panel]").forEach(function togglePanel(panel) {
      panel.hidden = panel.dataset.viewPanel !== view;
    });
    document.querySelectorAll("[data-view]").forEach(function toggleButton(button) {
      const active = button.dataset.view === view;
      button.classList.toggle("is-active", active);
      if (active) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
    });

    if (view !== "api") {
      renderInsightPanel(view);
    }
  }

  function renderManifest(manifest) {
    const plugins = manifest.plugins;
    const totalTypes = plugins.reduce(function sumTypes(total, plugin) { return total + plugin.types; }, 0);
    const totalMembers = plugins.reduce(function sumMembers(total, plugin) { return total + plugin.members; }, 0);

    elements.metricPlugins.textContent = formatNumber(plugins.length);
    elements.metricTypes.textContent = formatNumber(totalTypes);
    elements.metricMembers.textContent = formatNumber(totalMembers);

    elements.pluginSelect.replaceChildren();
    plugins.forEach(function addPluginOption(plugin) {
      const option = createElement("option", "", `${plugin.name} | ${formatNumber(plugin.types)} types | ${formatNumber(plugin.members)} members`);
      option.value = plugin.slug;
      elements.pluginSelect.appendChild(option);
    });
    elements.pluginSelect.disabled = false;

    elements.pluginRail.replaceChildren();
    elements.pluginRail.setAttribute("aria-busy", "false");
    plugins.forEach(function addRune(plugin) {
      const button = createElement("button", "dependency-rune");
      button.type = "button";
      button.dataset.plugin = plugin.slug;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", `${plugin.name}, ${formatNumber(plugin.types)} types, ${formatNumber(plugin.members)} members`);
      button.append(
        createElement("span", "rune-code", RUNE_CODES[plugin.slug] || `[${plugin.name.slice(0, 2).toUpperCase()}]`),
        createElement("span", "rune-name", plugin.name),
        createElement("span", "rune-counts", `${formatNumber(plugin.types)} T / ${formatNumber(plugin.members)} M`)
      );
      button.addEventListener("click", function selectRune() {
        selectPlugin(plugin.slug);
      });
      elements.pluginRail.appendChild(button);
    });

    elements.footerDataset.textContent = `Schema ${manifest.schemaVersion}. ${formatNumber(plugins.length)} plugin shards indexed on demand.`;
  }

  function updateRuneRail() {
    if (!state.pluginMeta) {
      return;
    }

    const context = PLUGIN_CONTEXT[state.pluginMeta.slug] || { relations: [] };
    const related = new Set(context.relations || []);
    document.querySelectorAll(".dependency-rune").forEach(function updateRune(button) {
      const active = button.dataset.plugin === state.pluginMeta.slug;
      button.classList.toggle("is-active", active);
      button.classList.toggle("is-related", !active && related.has(button.dataset.plugin));
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });

    const relationNames = (context.relations || []).map(function relationName(slug) {
      const plugin = state.manifest.plugins.find(function findPlugin(entry) { return entry.slug === slug; });
      return plugin ? plugin.name : slug;
    });
    const relationCopy = relationNames.length ? ` Integration paths: ${relationNames.join(", ")}.` : " No reviewed in-kit path is marked.";
    elements.railContext.textContent = `${state.pluginMeta.name}. ${formatNumber(state.pluginMeta.types)} types and ${formatNumber(state.pluginMeta.members)} members.${relationCopy}`;
  }

  function setApiControls(enabled) {
    [elements.search, elements.scope, elements.origin, elements.kind, elements.package, elements.deprecated, elements.pageSize].forEach(function toggleControl(control) {
      control.disabled = !enabled;
    });
  }

  function resetFilters() {
    elements.search.value = "";
    elements.scope.value = "all";
    elements.origin.value = "plugin-owned";
    elements.deprecated.checked = true;
    state.page = 1;
    state.pageSize = Number(elements.pageSize.value) || 24;
    state.selectedId = null;
  }

  function showLoadingState() {
    elements.symbolList.replaceChildren();
    elements.symbolList.setAttribute("aria-busy", "true");
    const skeleton = createElement("div", "skeleton-list");
    for (let index = 0; index < 6; index += 1) {
      const row = createElement("div", "skeleton-row");
      row.append(createElement("span", "skeleton-block"));
      const copy = createElement("span", "");
      copy.append(createElement("span", "skeleton-block is-wide"), createElement("span", "skeleton-block is-short"));
      row.appendChild(copy);
      skeleton.appendChild(row);
    }
    elements.symbolList.appendChild(skeleton);
    elements.resultCount.textContent = `Loading ${state.pluginMeta.name} symbols.`;
    elements.pageRange.textContent = "Building local index";
    elements.pageStatus.textContent = "Page 0 of 0";
    elements.previous.disabled = true;
    elements.next.disabled = true;
    renderEmptyDetail("Loading API shard", "The file is parsed by the browser without a server.");
  }

  function showErrorState(message, slug) {
    elements.symbolList.replaceChildren();
    elements.symbolList.setAttribute("aria-busy", "false");
    const errorState = createElement("div", "error-state");
    errorState.append(createElement("strong", "", "Local shard unavailable"), createElement("span", "", message));
    const retry = createElement("button", "error-action", "Retry shard");
    retry.type = "button";
    retry.addEventListener("click", function retryLoad() { selectPlugin(slug, true); });
    errorState.appendChild(retry);
    elements.symbolList.appendChild(errorState);
    elements.resultCount.textContent = "No symbols loaded.";
    elements.pageRange.textContent = "Check that the data folder remains beside index.html";
    renderEmptyDetail("Shard not loaded", message);
  }

  function renderEmptyDetail(title, body) {
    elements.symbolDetail.replaceChildren();
    const empty = createElement("div", "detail-empty");
    empty.append(createElement("span", "detail-rune", "{ }"));
    const heading = createElement("h3", "", title);
    heading.id = "detail-title";
    empty.append(heading, createElement("p", "", body));
    elements.symbolDetail.appendChild(empty);
  }

  function buildIndex(payload) {
    const index = [];
    payload.classes.forEach(function indexType(type, typeIndex) {
      const typeSignature = formatTypeSignature(type);
      index.push({
        id: type.id || `${payload.name}:type:${typeIndex}`,
        scope: "type",
        kind: type.kind || "class",
        packageName: type.package || "",
        name: type.simple_name || type.name,
        fullName: type.name,
        signature: typeSignature,
        origin: type.origin || "plugin-owned",
        deprecated: Boolean(type.deprecated),
        visibility: type.visibility || "public",
        type: type,
        member: null,
        searchText: [type.name, type.simple_name, type.package, type.kind, type.origin, type.super, (type.interfaces || []).join(" "), typeSignature].join(" ").toLowerCase()
      });

      (type.members || []).forEach(function indexMember(member, memberIndex) {
        const memberSignature = formatMemberSignature(member, type);
        index.push({
          id: member.id || `${payload.name}:member:${typeIndex}:${memberIndex}`,
          scope: "member",
          kind: member.kind || "member",
          packageName: type.package || "",
          name: member.name || member.jvm_name,
          fullName: `${type.name}.${member.name || member.jvm_name}`,
          signature: memberSignature,
          origin: type.origin || "plugin-owned",
          deprecated: Boolean(member.deprecated || type.deprecated),
          visibility: member.visibility || "public",
          type: type,
          member: member,
          searchText: [type.name, type.package, member.name, member.jvm_name, member.kind, member.return_type, (member.parameters || []).join(" "), member.descriptor, member.generic_signature, (member.modifiers || []).join(" "), memberSignature].join(" ").toLowerCase()
        });
      });
    });
    return index;
  }

  function formatTypeSignature(type) {
    const modifiers = (type.modifiers || []).join(" ");
    const parts = [modifiers, type.kind || "class", type.name].filter(Boolean);
    if (type.super && type.super !== "java.lang.Object") {
      parts.push("extends", type.super);
    }
    if (type.interfaces && type.interfaces.length) {
      parts.push("implements", type.interfaces.join(", "));
    }
    return parts.join(" ");
  }

  function formatMemberSignature(member, owner) {
    const modifiers = (member.modifiers || []).join(" ");
    const parameters = (member.parameters || []).join(", ");
    if (member.kind === "constructor") {
      return [modifiers, `${owner.simple_name || owner.name}(${parameters})`].filter(Boolean).join(" ");
    }
    if (member.kind === "field") {
      return [modifiers, member.return_type, member.name].filter(Boolean).join(" ");
    }
    return [modifiers, member.return_type, `${member.name || member.jvm_name}(${parameters})`].filter(Boolean).join(" ");
  }

  function populateFilters() {
    const kinds = Array.from(new Set(state.index.map(function getKind(item) { return item.kind; }))).sort(function sortKinds(left, right) {
      const leftIndex = KIND_ORDER.indexOf(left);
      const rightIndex = KIND_ORDER.indexOf(right);
      return (leftIndex === -1 ? KIND_ORDER.length : leftIndex) - (rightIndex === -1 ? KIND_ORDER.length : rightIndex) || left.localeCompare(right);
    });
    const packages = Array.from(new Set(state.index.map(function getPackage(item) { return item.packageName; }).filter(Boolean))).sort();

    elements.kind.replaceChildren(createOption("all", "Any kind"));
    kinds.forEach(function addKind(kind) { elements.kind.appendChild(createOption(kind, titleCase(kind))); });

    elements.package.replaceChildren(createOption("all", "All packages"));
    packages.forEach(function addPackage(packageName) { elements.package.appendChild(createOption(packageName, packageName)); });
  }

  function createOption(value, label) {
    const option = createElement("option", "", label);
    option.value = value;
    return option;
  }

  function titleCase(value) {
    const text = String(value || "");
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Unknown";
  }

  function applyFilters() {
    if (!state.pluginData) {
      return;
    }

    const queryParts = elements.search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const scope = elements.scope.value;
    const origin = elements.origin.value;
    const kind = elements.kind.value;
    const packageName = elements.package.value;
    const showDeprecated = elements.deprecated.checked;

    state.filtered = state.index.filter(function filterItem(item) {
      return (scope === "all" || item.scope === scope)
        && (origin === "all" || item.origin === origin)
        && (kind === "all" || item.kind === kind)
        && (packageName === "all" || item.packageName === packageName)
        && (showDeprecated || !item.deprecated)
        && queryParts.every(function matchPart(part) { return item.searchText.includes(part); });
    });

    const selectedStillVisible = state.filtered.some(function findSelected(item) { return item.id === state.selectedId; });
    if (!selectedStillVisible) {
      state.selectedId = state.filtered.length ? state.filtered[0].id : null;
    }
    renderResults();
  }

  function renderResults() {
    const total = state.filtered.length;
    const pageCount = total ? Math.ceil(total / state.pageSize) : 0;
    if (pageCount && state.page > pageCount) {
      state.page = pageCount;
    }
    const start = total ? (state.page - 1) * state.pageSize : 0;
    const end = Math.min(start + state.pageSize, total);

    elements.resultCount.textContent = `${formatNumber(total)} symbols match in ${state.pluginMeta.name}.`;
    elements.pageRange.textContent = total ? `${formatNumber(start + 1)} to ${formatNumber(end)} of ${formatNumber(total)}` : "No matching range";
    elements.pageStatus.textContent = `Page ${pageCount ? state.page : 0} of ${pageCount}`;
    elements.previous.disabled = !pageCount || state.page <= 1;
    elements.next.disabled = !pageCount || state.page >= pageCount;
    elements.symbolList.replaceChildren();
    elements.symbolList.setAttribute("aria-busy", "false");

    if (!total) {
      const empty = createElement("div", "empty-state");
      empty.append(createElement("strong", "", "No symbols match"), createElement("span", "", "Change the query or filters to widen the result set."));
      elements.symbolList.appendChild(empty);
      renderEmptyDetail("No symbol selected", "The current filters returned no API entries.");
      return;
    }

    const pageItems = state.filtered.slice(start, end);
    const selectedOnPage = pageItems.find(function findSelectedOnPage(item) { return item.id === state.selectedId; });
    const selectedItem = selectedOnPage || pageItems[0];
    state.selectedId = selectedItem.id;

    const fragment = document.createDocumentFragment();
    pageItems.forEach(function renderItem(item) {
      const entry = createElement("div", "symbol-entry");
      entry.setAttribute("role", "listitem");
      const row = createElement("button", "symbol-row");
      row.type = "button";
      row.dataset.symbolId = item.id;
      row.classList.toggle("is-selected", item.id === state.selectedId);
      row.setAttribute("aria-pressed", item.id === state.selectedId ? "true" : "false");
      const main = createElement("span", "symbol-main");
      main.append(createElement("span", "symbol-name", item.signature), createElement("span", "symbol-context", item.scope === "member" ? item.type.name : item.packageName));
      row.append(createElement("span", "symbol-kind", item.kind), main);
      if (item.deprecated) {
        row.appendChild(createElement("span", "deprecated-tag", "Deprecated"));
      }
      row.addEventListener("click", function selectSymbol() {
        state.selectedId = item.id;
        elements.symbolList.querySelectorAll(".symbol-row").forEach(function clearSelection(candidate) {
          const selected = candidate.dataset.symbolId === item.id;
          candidate.classList.toggle("is-selected", selected);
          candidate.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        renderSymbolDetail(item);
      });
      entry.appendChild(row);
      fragment.appendChild(entry);
    });
    elements.symbolList.appendChild(fragment);

    renderSymbolDetail(selectedItem);
  }

  function renderSymbolDetail(item) {
    elements.symbolDetail.replaceChildren();
    const header = createElement("header", "detail-header");
    const titleRow = createElement("div", "detail-title-row");
    const titleBlock = createElement("div", "");
    const heading = createElement("h3", "", item.scope === "type" ? item.name : `${item.type.simple_name || item.type.name}.${item.name}`);
    heading.id = "detail-title";
    titleBlock.append(heading, createElement("p", "symbol-context", item.scope === "type" ? item.fullName : item.type.name));
    titleRow.append(titleBlock, createElement("span", "detail-kind", item.kind));
    header.append(titleRow);
    if (item.deprecated) {
      header.appendChild(createElement("span", "deprecated-tag", "Deprecated API"));
    }
    elements.symbolDetail.append(header, createElement("div", "signature-block", item.signature));

    const details = createElement("dl", "detail-grid");
    if (item.scope === "type") {
      appendDetailField(details, "Plugin", state.pluginData.name);
      appendDetailField(details, "Origin", item.type.origin || "plugin-owned");
      appendDetailField(details, "Package", item.type.package);
      appendDetailField(details, "Visibility", item.type.visibility);
      appendDetailField(details, "Modifiers", item.type.modifiers);
      appendDetailField(details, "Super type", item.type.super);
      appendDetailField(details, "Interfaces", item.type.interfaces);
      appendDetailField(details, "Generic signature", item.type.generic_signature);
      appendDetailField(details, "Members", formatNumber((item.type.members || []).length));
      appendDetailField(details, "Source path", item.type.source_path);
      appendDetailField(details, "JAR entry", item.type.jar_entry);
      appendDetailField(details, "Java release", item.type.java_release);
      appendDetailField(details, "Class version", item.type.major_version);
    } else {
      const member = item.member;
      appendDetailField(details, "Owner", item.type.name);
      appendDetailField(details, "Origin", item.type.origin || "plugin-owned");
      appendDetailField(details, "Visibility", member.visibility);
      appendDetailField(details, "Modifiers", member.modifiers);
      appendDetailField(details, "Return type", member.return_type);
      appendDetailField(details, "Parameters", member.parameters);
      appendDetailField(details, "Throws", member.throws);
      appendDetailField(details, "Descriptor", member.descriptor);
      appendDetailField(details, "Generic signature", member.generic_signature);
      appendDetailField(details, "Constant", member.constant);
      appendDetailField(details, "Bridge", member.bridge);
      appendDetailField(details, "Synthetic", member.synthetic);
      appendDetailField(details, "Source path", item.type.source_path);
    }
    elements.symbolDetail.appendChild(details);
  }

  function appendDetailField(list, label, value) {
    if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)) {
      return;
    }
    const row = createElement("div", "detail-field");
    row.appendChild(createElement("dt", "", label));
    const description = createElement("dd", "");
    if (Array.isArray(value)) {
      const tags = createElement("div", "tag-list");
      value.forEach(function addTag(entry) { tags.appendChild(createElement("span", "tag", entry)); });
      description.appendChild(tags);
    } else if (typeof value === "object") {
      description.textContent = JSON.stringify(value);
    } else {
      description.textContent = String(value);
    }
    row.appendChild(description);
    list.appendChild(row);
  }

  async function selectPlugin(slug, forceReload) {
    if (!state.manifest) {
      return;
    }
    const meta = state.manifest.plugins.find(function findPlugin(plugin) { return plugin.slug === slug; });
    if (!meta || (!forceReload && state.loadingSlug === slug)) {
      return;
    }
    if (!forceReload && state.pluginMeta && state.pluginMeta.slug === slug && state.pluginData) {
      return;
    }

    const token = state.loadToken + 1;
    state.loadToken = token;
    state.loadingSlug = slug;
    state.pluginMeta = meta;
    state.pluginData = null;
    state.index = [];
    state.filtered = [];
    resetFilters();
    elements.pluginSelect.value = slug;
    elements.activePluginName.textContent = meta.name;
    updateRuneRail();
    renderInsightPanels();
    setApiControls(false);
    setStatus("Loading", "");
    showLoadingState();

    try {
      const payload = await loadPluginShard(meta);
      if (token !== state.loadToken) {
        return;
      }
      state.pluginData = payload;
      state.index = buildIndex(payload);
      populateFilters();
      setApiControls(true);
      state.filtered = state.index.slice();
      state.selectedId = state.filtered.length ? state.filtered[0].id : null;
      setStatus("Ready", "ready");
      elements.footerDataset.textContent = `${payload.name}. ${payload.jar}. Loaded from ${meta.file}.`;
      applyFilters();
    } catch (error) {
      if (token !== state.loadToken) {
        return;
      }
      setStatus("Error", "error");
      showErrorState(error && error.message ? error.message : "The local shard could not be loaded.", slug);
    } finally {
      if (token === state.loadToken) {
        state.loadingSlug = null;
      }
    }
  }

  function getFallbackInsight(section) {
    const plugin = state.pluginMeta || (state.manifest && state.manifest.plugins[0]);
    const context = plugin && PLUGIN_CONTEXT[plugin.slug] ? PLUGIN_CONTEXT[plugin.slug] : {
      layer: "Plugin API",
      role: "Published Java types and members from the selected local shard.",
      relations: [],
      architecture: "The selected plugin exposes bytecode symbols for offline inspection.",
      features: []
    };

    if (section === "overview") {
      return {
        title: `${plugin.name} overview`,
        intro: context.role,
        source: "Local manifest and source review fallback",
        items: [
          { title: "System layer", body: context.layer, meta: "Responsibility" },
          { title: "Published API", body: `${formatNumber(plugin.types)} public or protected types and ${formatNumber(plugin.members)} members.`, meta: plugin.namespaces.join(", ") },
          { title: "Integration shape", body: context.relations.length ? `Reviewed paths connect to ${context.relations.map(function nameRelation(slug) { const match = state.manifest.plugins.find(function findEntry(entry) { return entry.slug === slug; }); return match ? match.name : slug; }).join(", ")}.` : "No reviewed in-kit relation is marked in the fallback map.", meta: "Rune rail" },
          { title: "Coverage contract", body: "The explorer publishes public and protected namespace signatures. Origin labels separate plugin-owned declarations from bundled third-party code.", meta: "Bytecode inventory" }
        ]
      };
    }

    if (section === "architecture") {
      return {
        title: "RPG runtime architecture",
        intro: `${plugin.name} focus: ${context.architecture}`,
        source: "Cross-plugin source review fallback",
        items: ARCHITECTURE_FLOW
      };
    }

    if (section === "features") {
      return {
        title: `${plugin.name} feature inventory`,
        intro: `Capability groups inferred from the reviewed ${context.layer.toLowerCase()} code and resources.`,
        source: "Plugin-specific fallback",
        items: context.features.map(function featureItem(feature, index) {
          return { title: feature, body: featureDescription(plugin.slug, index), meta: `${plugin.name} capability` };
        })
      };
    }

    return {
      title: "Addon Lab",
      intro: "Original compositions built from reviewed extension points. These are proposed addons, not existing end-to-end plugin features.",
      source: "MMO-family and ModelEngine research fallback",
      items: ADDON_IDEAS
    };
  }

  function featureDescription(slug, index) {
    const context = PLUGIN_CONTEXT[slug];
    const feature = context && context.features[index] ? context.features[index] : "Plugin capability";
    return `${feature} is represented by searchable types and members in the selected shard. Inspect signatures before binding an addon to implementation packages.`;
  }

  function getCuratedInsight(section) {
    const source = global.MinecraftRPGInsights;
    if (!source || typeof source !== "object") {
      return null;
    }

    const slug = state.pluginMeta ? state.pluginMeta.slug : "";
    const aliases = section === "addons" ? ["addons", "addon", "addonIdeas"] : [section];
    const pluginBlock = source.plugins && (source.plugins[slug] || source.plugins[state.pluginMeta.name])
      ? (source.plugins[slug] || source.plugins[state.pluginMeta.name])
      : (source[slug] || source[state.pluginMeta.name]);
    const globalBlock = source.global && typeof source.global === "object" ? source.global : source;

    for (const alias of aliases) {
      if (pluginBlock && pluginBlock[alias] !== undefined) {
        return pluginBlock[alias];
      }
      if (globalBlock && globalBlock[alias] !== undefined) {
        return globalBlock[alias];
      }
    }
    return null;
  }

  function normalizeInsight(raw, fallback) {
    if (raw === null || raw === undefined) {
      return fallback;
    }
    if (typeof raw === "string") {
      return { title: fallback.title, intro: raw, source: "window.MinecraftRPGInsights", items: fallback.items };
    }
    if (Array.isArray(raw)) {
      return { title: fallback.title, intro: fallback.intro, source: "window.MinecraftRPGInsights", items: raw };
    }
    if (typeof raw !== "object") {
      return fallback;
    }

    let candidateItems = firstDefined(raw.items, raw.sections, raw.features, raw.steps, raw.ideas, raw.addons, raw.entries);
    if (candidateItems === undefined) {
      const contentKeys = Object.keys(raw).filter(function filterMetadata(key) {
        return !["title", "name", "intro", "summary", "description", "source"].includes(key);
      });
      candidateItems = contentKeys.reduce(function collectContent(collection, key) {
        collection[key] = raw[key];
        return collection;
      }, {});
    }
    return {
      title: firstDefined(raw.title, raw.name, fallback.title),
      intro: firstDefined(raw.intro, raw.summary, raw.description, fallback.intro),
      source: firstDefined(raw.source, "window.MinecraftRPGInsights"),
      items: normalizeItemCollection(candidateItems)
    };
  }

  function firstDefined() {
    for (let index = 0; index < arguments.length; index += 1) {
      if (arguments[index] !== undefined && arguments[index] !== null) {
        return arguments[index];
      }
    }
    return undefined;
  }

  function normalizeItemCollection(value) {
    if (Array.isArray(value)) {
      return value;
    }
    if (value && typeof value === "object") {
      return Object.keys(value).map(function mapEntry(key) {
        const entry = value[key];
        return typeof entry === "object" && entry !== null ? Object.assign({ title: key }, entry) : { title: key, body: String(entry) };
      });
    }
    if (typeof value === "string") {
      return [value];
    }
    return [];
  }

  function normalizeInsightItem(item, index) {
    if (typeof item === "string") {
      return { title: item, body: "", meta: "" };
    }
    if (!item || typeof item !== "object") {
      return { title: `Entry ${index + 1}`, body: String(item || ""), meta: "" };
    }
    return {
      title: firstDefined(item.title, item.name, item.label, `Entry ${index + 1}`),
      body: textValue(firstDefined(item.body, item.description, item.summary, item.value, item.detail, "")),
      meta: textValue(firstDefined(item.meta, item.api, item.dependencies, item.tags, item.role, ""))
    };
  }

  function textValue(value) {
    if (Array.isArray(value)) {
      return value.map(textValue).filter(Boolean).join(", ");
    }
    if (value && typeof value === "object") {
      return Object.keys(value).map(function mapValue(key) { return `${key}: ${textValue(value[key])}`; }).join("; ");
    }
    return value === null || value === undefined ? "" : String(value);
  }

  function renderInsightPanel(section) {
    const container = document.getElementById(`${section}-content`);
    if (!container || !state.pluginMeta) {
      return;
    }
    const fallback = getFallbackInsight(section);
    const curated = getCuratedInsight(section);
    const insight = normalizeInsight(curated, fallback);
    container.replaceChildren();

    const header = createElement("header", "insight-header");
    const titleBlock = createElement("div", "");
    const heading = createElement("h2", "", insight.title);
    heading.id = `${section}-heading`;
    titleBlock.append(heading, createElement("p", "insight-source", `Source: ${insight.source}`));
    header.append(titleBlock, createElement("p", "insight-intro", insight.intro));
    container.appendChild(header);

    const items = normalizeItemCollection(insight.items);
    if (!items.length) {
      container.appendChild(createElement("p", "insight-empty", "No curated entries are available for this panel."));
      return;
    }

    const list = createElement("div", "insight-list");
    items.forEach(function renderInsightItem(item, index) {
      const normalized = normalizeInsightItem(item, index);
      const row = createElement("article", "insight-row");
      row.append(createElement("h3", "", normalized.title), createElement("p", "", normalized.body), createElement("span", "insight-meta", normalized.meta));
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function renderInsightPanels() {
    ["overview", "architecture", "features", "addons"].forEach(renderInsightPanel);
  }

  kit.refreshInsights = renderInsightPanels;

  function showFatalError(message) {
    setStatus("Error", "error");
    elements.pluginRail.replaceChildren();
    elements.pluginRail.setAttribute("aria-busy", "false");
    const error = createElement("div", "error-state");
    error.append(createElement("strong", "", "Manifest unavailable"), createElement("span", "", message));
    elements.pluginRail.appendChild(error);
    elements.railContext.textContent = "Keep index.html, app.js, styles.css, and the data folder together.";
    showErrorState(message, "");
  }

  async function boot() {
    cacheElements();
    bindEvents();
    setStatus("Loading manifest", "");

    try {
      if (!global.MinecraftRPGManifest) {
        await injectScript("data/manifest.js", "local manifest");
      }
      const manifest = global.MinecraftRPGManifest;
      if (!manifest || !Array.isArray(manifest.plugins) || !manifest.plugins.length) {
        throw new Error("data/manifest.js did not expose a plugin list.");
      }
      state.manifest = manifest;
      if (manifest.insightsFile && !global.MinecraftRPGInsights) {
        try {
          await injectScript(manifest.insightsFile, "curated insights");
        } catch (insightError) {
          elements.liveStatus.textContent = "Curated insights unavailable; using built-in review summaries.";
        }
      }
      renderManifest(manifest);
      await selectPlugin(manifest.plugins[0].slug);
    } catch (error) {
      showFatalError(error && error.message ? error.message : "The local manifest could not be read.");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})(window);
