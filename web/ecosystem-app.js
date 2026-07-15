(function bootstrapMinecraftKitAtlas(global) {
  "use strict";

  const data = global.MinecraftKitEcosystem;
  const renderers = global.MinecraftKitAtlasRenderers;
  const VIEWS = new Set(["overview", "sources", "versions"]);
  const PRIORITIES = new Set(["all", "P0", "P1", "P2"]);
  const POLICIES = new Set(["all", "index", "derive", "metadata-only", "link-only"]);
  const LIFECYCLES = new Set(["all", "current", "archived"]);
  const VERSION_TYPES = new Set(["all", "release", "snapshot", "old_alpha", "old_beta"]);
  const SOURCE_SORTS = new Set(["priority", "stars", "freshness", "name"]);
  const PAGE_SIZE = 100;

  const state = {
    view: "overview",
    sourceQuery: "",
    domain: "all",
    priority: "all",
    policy: "all",
    lifecycle: "all",
    license: "all",
    sourceSort: "priority",
    versionQuery: "",
    versionType: "all",
    versionLimit: PAGE_SIZE
  };
  const elements = {};

  function byId(id) {
    return document.getElementById(id);
  }

  function cacheElements() {
    elements.metricSourceCount = byId("metric-source-count");
    elements.metricVersionCount = byId("metric-version-count");
    elements.metricDomainCount = byId("metric-domain-count");
    elements.domainGrid = byId("domain-grid");
    elements.provenanceList = byId("provenance-list");
    elements.distributionList = byId("distribution-list");
    elements.footerFreshness = byId("footer-freshness");
    elements.sourceFilterForm = byId("source-filter-form");
    elements.sourceQuery = byId("source-query");
    elements.domainFilter = byId("domain-filter");
    elements.priorityFilter = byId("priority-filter");
    elements.policyFilter = byId("policy-filter");
    elements.lifecycleFilter = byId("lifecycle-filter");
    elements.licenseFilter = byId("license-filter");
    elements.sourceSort = byId("source-sort");
    elements.resetSourceFilters = byId("reset-source-filters");
    elements.sourceResultCount = byId("source-result-count");
    elements.sourceList = byId("source-list");
    elements.sourceEmpty = byId("source-empty");
    elements.versionMetrics = byId("version-metrics");
    elements.latestVersions = byId("latest-versions");
    elements.releaseCapabilityProfile = byId("release-capability-profile");
    elements.versionQuery = byId("version-query");
    elements.versionTypeFilter = byId("version-type-filter");
    elements.versionResultCount = byId("version-result-count");
    elements.versionHistoryBody = byId("version-history-body");
    elements.loadMoreVersions = byId("load-more-versions");
    elements.atlasStatus = byId("atlas-status");
  }

  function appendOption(select, value, label) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }

  function populateFilters() {
    data.domains.forEach(function addDomain(domain) {
      appendOption(elements.domainFilter, domain.id, `${domain.name} / ${domain.route}`);
    });
    Object.keys(data.summary.licenseCounts).sort().forEach(function addLicense(license) {
      appendOption(elements.licenseFilter, license, `${license} (${data.summary.licenseCounts[license]})`);
    });
  }

  function normalized(value) {
    return String(value || "").normalize("NFKD").toLocaleLowerCase("en-US").trim();
  }

  function allowed(value, choices, fallback) {
    return choices.has(value) ? value : fallback;
  }

  function readHash() {
    const params = new URLSearchParams(global.location.hash.replace(/^#/, ""));
    const domainIds = new Set(["all", ...data.domains.map(function id(domain) { return domain.id; })]);
    const licenses = new Set(["all", ...Object.keys(data.summary.licenseCounts)]);
    state.view = allowed(params.get("view"), VIEWS, "overview");
    state.sourceQuery = params.get("q") || "";
    state.domain = allowed(params.get("domain"), domainIds, "all");
    state.priority = allowed(params.get("priority"), PRIORITIES, "all");
    state.policy = allowed(params.get("policy"), POLICIES, "all");
    state.lifecycle = allowed(params.get("state"), LIFECYCLES, "all");
    state.license = allowed(params.get("license"), licenses, "all");
    state.sourceSort = allowed(params.get("sort"), SOURCE_SORTS, "priority");
    state.versionQuery = params.get("vq") || "";
    state.versionType = allowed(params.get("channel"), VERSION_TYPES, "all");
    state.versionLimit = PAGE_SIZE;
  }

  function addHashValue(params, key, value, defaultValue) {
    if (value !== defaultValue && value !== "") {
      params.set(key, value);
    }
  }

  function writeHash() {
    const params = new URLSearchParams();
    addHashValue(params, "view", state.view, "overview");
    addHashValue(params, "q", state.sourceQuery, "");
    addHashValue(params, "domain", state.domain, "all");
    addHashValue(params, "priority", state.priority, "all");
    addHashValue(params, "policy", state.policy, "all");
    addHashValue(params, "state", state.lifecycle, "all");
    addHashValue(params, "license", state.license, "all");
    addHashValue(params, "sort", state.sourceSort, "priority");
    addHashValue(params, "vq", state.versionQuery, "");
    addHashValue(params, "channel", state.versionType, "all");
    const encoded = params.toString();
    const nextLocation = `${global.location.pathname}${global.location.search}${encoded ? `#${encoded}` : ""}`;
    global.history.replaceState(null, "", nextLocation);
  }

  function applyStateToControls() {
    elements.sourceQuery.value = state.sourceQuery;
    elements.domainFilter.value = state.domain;
    elements.priorityFilter.value = state.priority;
    elements.policyFilter.value = state.policy;
    elements.lifecycleFilter.value = state.lifecycle;
    elements.licenseFilter.value = state.license;
    elements.sourceSort.value = state.sourceSort;
    elements.versionQuery.value = state.versionQuery;
    elements.versionTypeFilter.value = state.versionType;
  }

  function setView(view, updateLocation) {
    state.view = allowed(view, VIEWS, "overview");
    document.querySelectorAll("[data-view-panel]").forEach(function updatePanel(panel) {
      panel.hidden = panel.dataset.viewPanel !== state.view;
    });
    document.querySelectorAll("[data-view]").forEach(function updateButton(button) {
      if (button.dataset.view === state.view) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
    });
    if (updateLocation) {
      writeHash();
    }
  }

  function sourceHaystack(source) {
    const github = source.github;
    const release = github.latest_release;
    const license = renderers.sourceLicense(source);
    return normalized([
      source.id,
      source.name,
      source.repository,
      source.rationale,
      github.description,
      source.domains.join(" "),
      source.priority,
      source.ingestion_policy,
      license,
      release ? release.tag : ""
    ].join(" "));
  }

  function compareSources(left, right) {
    if (state.sourceSort === "stars") {
      return (Number(right.github.stars) || 0) - (Number(left.github.stars) || 0) || left.name.localeCompare(right.name);
    }
    if (state.sourceSort === "freshness") {
      return (Date.parse(right.github.pushed_at) || 0) - (Date.parse(left.github.pushed_at) || 0) || left.name.localeCompare(right.name);
    }
    if (state.sourceSort === "name") {
      return left.name.localeCompare(right.name);
    }
    const rank = { P0: 0, P1: 1, P2: 2 };
    return rank[left.priority] - rank[right.priority] || left.name.localeCompare(right.name);
  }

  function filteredSources() {
    const query = normalized(state.sourceQuery);
    return data.sources.filter(function includeSource(source) {
      const archived = Boolean(source.github.archived);
      return (!query || sourceHaystack(source).includes(query))
        && (state.domain === "all" || source.domains.includes(state.domain))
        && (state.priority === "all" || source.priority === state.priority)
        && (state.policy === "all" || source.ingestion_policy === state.policy)
        && (state.lifecycle === "all" || (state.lifecycle === "archived") === archived)
        && (state.license === "all" || renderers.sourceLicense(source) === state.license);
    }).sort(compareSources);
  }

  function renderSourceState() {
    const sources = filteredSources();
    renderers.renderSources(elements, sources);
    elements.sourceResultCount.textContent = `${renderers.number(sources.length)} of ${renderers.number(data.sources.length)} reviewed sources match.`;
  }

  function filteredVersions() {
    const query = normalized(state.versionQuery);
    return data.versions.history.filter(function includeVersion(version) {
      return (!query || normalized(version.id).includes(query))
        && (state.versionType === "all" || version.type === state.versionType);
    });
  }

  function renderVersionState() {
    renderers.renderVersionHistory(elements, filteredVersions(), state.versionLimit);
  }

  function selectDomain(domain) {
    state.domain = domain;
    elements.domainFilter.value = domain;
    setView("sources", false);
    renderSourceState();
    writeHash();
    elements.sourceResultCount.focus({ preventScroll: true });
    document.getElementById("view-sources").scrollIntoView({ block: "start" });
  }

  function resetSources() {
    state.sourceQuery = "";
    state.domain = "all";
    state.priority = "all";
    state.policy = "all";
    state.lifecycle = "all";
    state.license = "all";
    state.sourceSort = "priority";
    applyStateToControls();
    renderSourceState();
    writeHash();
    elements.atlasStatus.textContent = "Source filters reset.";
  }

  function bindEvents() {
    document.querySelectorAll("[data-view]").forEach(function bindView(button) {
      button.addEventListener("click", function changeView() {
        setView(button.dataset.view, true);
        document.getElementById(`view-${button.dataset.view}`).scrollIntoView({ block: "start" });
      });
    });
    elements.sourceFilterForm.addEventListener("submit", function preventSubmit(event) {
      event.preventDefault();
    });
    elements.sourceQuery.addEventListener("input", function updateQuery() {
      state.sourceQuery = elements.sourceQuery.value;
      renderSourceState();
      writeHash();
    });
    [
      [elements.domainFilter, "domain"],
      [elements.priorityFilter, "priority"],
      [elements.policyFilter, "policy"],
      [elements.lifecycleFilter, "lifecycle"],
      [elements.licenseFilter, "license"],
      [elements.sourceSort, "sourceSort"]
    ].forEach(function bindSourceControl(binding) {
      binding[0].addEventListener("change", function updateSourceControl() {
        state[binding[1]] = binding[0].value;
        renderSourceState();
        writeHash();
      });
    });
    elements.resetSourceFilters.addEventListener("click", resetSources);
    elements.versionQuery.addEventListener("input", function updateVersionQuery() {
      state.versionQuery = elements.versionQuery.value;
      state.versionLimit = PAGE_SIZE;
      renderVersionState();
      writeHash();
    });
    elements.versionTypeFilter.addEventListener("change", function updateVersionType() {
      state.versionType = elements.versionTypeFilter.value;
      state.versionLimit = PAGE_SIZE;
      renderVersionState();
      writeHash();
    });
    elements.loadMoreVersions.addEventListener("click", function loadMoreVersions() {
      state.versionLimit += PAGE_SIZE;
      renderVersionState();
    });
    document.addEventListener("keydown", function focusSearch(event) {
      const target = event.target;
      const isTyping = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
      if (event.key === "/" && !isTyping && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        setView("sources", true);
        elements.sourceQuery.focus();
      }
    });
    global.addEventListener("hashchange", function restoreHash() {
      readHash();
      applyStateToControls();
      setView(state.view, false);
      renderSourceState();
      renderVersionState();
    });
  }

  function renderFailure(message) {
    const error = renderers && renderers.createElement
      ? renderers.createElement("p", "dataset-error", message)
      : document.createTextNode(message);
    elements.domainGrid.replaceChildren(error);
    elements.metricSourceCount.textContent = "Unavailable";
    elements.metricVersionCount.textContent = "Unavailable";
    elements.atlasStatus.textContent = message;
  }

  function validDataset() {
    return data && renderers && data.schemaVersion === 1
      && Array.isArray(data.domains) && Array.isArray(data.sources)
      && data.versions && Array.isArray(data.versions.history)
      && data.releaseCapabilities && Array.isArray(data.releaseCapabilities.releases);
  }

  function initialize() {
    cacheElements();
    if (!validDataset()) {
      renderFailure("The generated ecosystem dataset is missing or invalid. Run scripts/render_ecosystem_web.py.");
      return;
    }
    populateFilters();
    readHash();
    applyStateToControls();
    renderers.renderOverview(elements, data, selectDomain);
    renderers.renderVersions(elements, data);
    renderSourceState();
    renderVersionState();
    setView(state.view, false);
    bindEvents();
    elements.atlasStatus.textContent = `Atlas ready with ${renderers.number(data.sources.length)} pinned sources.`;
    if (state.view !== "overview") {
      global.requestAnimationFrame(function revealRestoredView() {
        document.getElementById(`view-${state.view}`).scrollIntoView({ block: "start" });
      });
    }
  }

  initialize();
}(window));
