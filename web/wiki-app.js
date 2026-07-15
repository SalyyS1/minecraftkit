(function () {
  "use strict";

  var data = window.SalyyyMinecraftKitWiki;
  var liveStatus = document.getElementById("live-status");
  if (!data || !Array.isArray(data.routes)) {
    liveStatus.textContent = "Local wiki payload is unavailable.";
    return;
  }

  var routeIds = new Set(data.routes.map(function (route) { return route.id; }));
  var state = readState();
  var search = document.getElementById("wiki-search");
  var filter = document.getElementById("route-filter");
  var routeGrid = document.getElementById("route-grid");
  var chapterGrid = document.getElementById("chapter-grid");
  var installerGrid = document.getElementById("installer-grid");
  var routeSection = document.getElementById("routes");
  var handbookSection = document.getElementById("handbook");
  var installSection = document.getElementById("install");
  var emptyState = document.getElementById("empty-state");
  var resultStatus = document.getElementById("result-status");
  var dialog = document.getElementById("route-dialog");
  var routeDetail = document.getElementById("route-detail");
  var ignoreDialogClose = false;

  function readState() {
    var params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    var language = params.get("lang");
    var routeFilter = params.get("filter");
    var openRoute = params.get("route");
    return {
      lang: language === "en" ? "en" : "vi",
      q: params.get("q") || "",
      filter: routeFilter && routeIds.has(routeFilter) ? routeFilter : "all",
      route: openRoute && routeIds.has(openRoute) ? openRoute : null
    };
  }

  function commit(push) {
    var params = new URLSearchParams();
    params.set("lang", state.lang);
    if (state.q) { params.set("q", state.q); }
    if (state.filter !== "all") { params.set("filter", state.filter); }
    if (state.route) { params.set("route", state.route); }
    var next = new URL(window.location.href);
    next.hash = params.toString();
    window.history[push ? "pushState" : "replaceState"](null, "", next);
    render();
  }

  function t(key) { return data.ui[state.lang][key] || key; }
  function local(item) { return item.content[state.lang]; }
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }
  function searchable(value, output) {
    if (typeof value === "string") { output.push(value); return; }
    if (Array.isArray(value)) { value.forEach(function (item) { searchable(item, output); }); return; }
    if (value && typeof value === "object") {
      Object.keys(value).forEach(function (key) { searchable(value[key], output); });
    }
  }
  function matches(item, extra) {
    if (!state.q.trim()) { return true; }
    var words = [];
    searchable(item, words);
    searchable(extra, words);
    return normalize(words.join(" ")).indexOf(normalize(state.q.trim())) !== -1;
  }
  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function renderLabels() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach(function (node) {
      node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
    });
    search.placeholder = t("search_placeholder");
    search.value = state.q;
    document.querySelectorAll("[data-language]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.language === state.lang));
    });
  }

  function renderFilter() {
    var options = [element("option", "", t("all_routes"))];
    options[0].value = "all";
    data.routes.forEach(function (route) {
      var option = element("option", "", route.route + " — " + local(route).title);
      option.value = route.id;
      options.push(option);
    });
    filter.replaceChildren.apply(filter, options);
    filter.value = state.filter;
  }

  function renderRoutes() {
    var visible = data.routes.filter(function (route) {
      return (state.filter === "all" || state.filter === route.id) && matches(local(route), route.keywords);
    });
    var cards = visible.map(function (route) {
      var content = local(route);
      var card = element("button", "route-card");
      card.type = "button";
      card.dataset.routeId = route.id;
      card.setAttribute("aria-label", t("open_route") + ": " + route.route + " " + content.title);
      card.append(element("span", "route-code", "/" + route.route));
      var body = element("span", "route-card-body");
      body.append(element("h3", "", content.title), element("p", "", content.what));
      card.append(body);
      var action = element("span", "route-action");
      action.append(element("span", "", t("open_route")), element("b", "", "↗"));
      card.append(action);
      card.addEventListener("click", function () {
        state.route = route.id;
        commit(true);
      });
      return card;
    });
    routeGrid.replaceChildren.apply(routeGrid, cards);
    routeSection.hidden = visible.length === 0;
    return visible.length;
  }

  function renderChapters() {
    var visible = data.chapters.filter(function (chapter) { return matches(local(chapter), chapter.keywords); });
    var cards = visible.map(function (chapter, index) {
      var content = local(chapter);
      var card = element("article", "chapter-card");
      card.append(element("span", "chapter-index", "SYS::" + String(index + 1).padStart(2, "0")));
      card.append(element("h3", "", content.title), element("p", "chapter-summary", content.summary));
      var list = element("ul");
      content.points.forEach(function (point) { list.append(element("li", "", point)); });
      card.append(list);
      return card;
    });
    chapterGrid.replaceChildren.apply(chapterGrid, cards);
    handbookSection.hidden = visible.length === 0;
    return visible.length;
  }

  function copyText(text, button) {
    var copy = navigator.clipboard && navigator.clipboard.writeText
      ? navigator.clipboard.writeText(text)
      : new Promise(function (resolve, reject) {
          var field = element("textarea", "visually-hidden");
          field.value = text;
          document.body.append(field);
          field.select();
          try { document.execCommand("copy") ? resolve() : reject(new Error("copy")); }
          catch (error) { reject(error); }
          field.remove();
        });
    copy.then(function () {
      button.textContent = t("copied");
      liveStatus.textContent = t("copied");
      window.setTimeout(function () { button.textContent = t("copy"); }, 1400);
    }).catch(function () {
      liveStatus.textContent = t("copy_failed");
      button.textContent = t("copy_failed");
    });
  }

  function copyButton(text) {
    var button = element("button", "copy-button", t("copy"));
    button.type = "button";
    button.setAttribute("aria-label", t("copy"));
    button.addEventListener("click", function () { copyText(text, button); });
    return button;
  }

  function renderInstallers() {
    var visible = data.installers.filter(function (installer) {
      return matches(local(installer), [installer.target, "npx minecraftkit install"]);
    });
    var cards = visible.map(function (installer) {
      var content = local(installer);
      var card = element("article", "installer-card");
      card.append(element("span", "target-label", "TARGET::" + installer.target));
      card.append(element("h3", "", content.title), element("p", "", content.description));
      var npmCommand = "npx minecraftkit install --target " + installer.target;
      var command = element("pre", "command-block");
      command.append(element("code", "", npmCommand), copyButton(npmCommand));
      card.append(command);
      return card;
    });
    installerGrid.replaceChildren.apply(installerGrid, cards);
    installSection.hidden = visible.length === 0;
    return visible.length;
  }

  function detailList(title, values, ordered, extraClass) {
    var section = element("section", "detail-section" + (extraClass ? " " + extraClass : ""));
    section.append(element("h3", "", title));
    var list = element(ordered ? "ol" : "ul");
    values.forEach(function (value) { list.append(element("li", "", value)); });
    section.append(list);
    return section;
  }

  function renderDialog() {
    var route = state.route && data.routes.find(function (item) { return item.id === state.route; });
    if (!route) {
      if (dialog.open) { ignoreDialogClose = true; dialog.close(); }
      return;
    }
    var content = local(route);
    var header = element("header", "dialog-header");
    var heading = element("div");
    heading.append(element("span", "route-code", "/" + route.route));
    var title = element("h2", "", content.title);
    title.id = "dialog-route-title";
    heading.append(title);
    var close = element("button", "dialog-close", "×");
    close.type = "button";
    close.setAttribute("aria-label", t("close_route"));
    close.addEventListener("click", function () { dialog.close(); });
    header.append(heading, close);
    var grid = element("div", "detail-grid");
    grid.append(
      detailList(t("when"), content.when, false),
      detailList(t("inputs"), content.inputs, false),
      detailList(t("workflow"), content.workflow, true),
      detailList(t("outputs"), content.outputs, false),
      detailList(t("guardrails"), content.guardrails, false)
    );
    var examples = element("section", "detail-section detail-examples");
    examples.append(element("h3", "", t("examples")));
    content.examples.forEach(function (prompt) {
      var row = element("div", "prompt-row");
      row.append(element("code", "", prompt), copyButton(prompt));
      examples.append(row);
    });
    grid.append(examples);
    routeDetail.replaceChildren(header, element("p", "route-what", content.what), grid);
    if (!dialog.open) { dialog.showModal(); }
  }

  function focusRouteCard(routeId) {
    var card = Array.prototype.find.call(
      routeGrid.querySelectorAll(".route-card"),
      function (candidate) { return candidate.dataset.routeId === routeId; }
    );
    if (card) { card.focus(); }
  }

  function render() {
    renderLabels();
    renderFilter();
    var total = renderRoutes() + renderChapters() + renderInstallers();
    resultStatus.textContent = String(total).padStart(2, "0") + " " + t("results_status");
    emptyState.hidden = total !== 0;
    renderDialog();
  }

  document.querySelectorAll("[data-language]").forEach(function (button) {
    button.addEventListener("click", function () { state.lang = button.dataset.language; commit(false); });
  });
  document.querySelectorAll("[data-copy-command]").forEach(function (button) {
    button.addEventListener("click", function () { copyText(button.dataset.copyCommand, button); });
  });
  search.addEventListener("input", function () { state.q = search.value; commit(false); });
  filter.addEventListener("change", function () { state.filter = filter.value; commit(false); });
  dialog.addEventListener("close", function () {
    if (ignoreDialogClose) { ignoreDialogClose = false; return; }
    if (state.route) {
      var routeToRestore = state.route;
      state.route = null;
      commit(false);
      focusRouteCard(routeToRestore);
    }
  });
  document.querySelectorAll('.primary-nav a[href^="#"]').forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      var target = document.querySelector(link.getAttribute("href"));
      if (target) { target.scrollIntoView({ block: "start" }); }
    });
  });
  document.querySelector(".brand").addEventListener("click", function (event) {
    event.preventDefault();
    window.scrollTo({ top: 0 });
  });
  document.addEventListener("keydown", function (event) {
    var tag = document.activeElement && document.activeElement.tagName;
    if (event.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(tag || "")) {
      event.preventDefault();
      search.focus();
    }
  });
  window.addEventListener("popstate", function () {
    var routeToRestore = state.route;
    state = readState();
    render();
    if (routeToRestore && !state.route) { focusRouteCard(routeToRestore); }
  });
  commit(false);
}());
