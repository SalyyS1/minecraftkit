(function () {
  "use strict";

  var page = document.body.dataset.page || "wiki";
  var pages = [
    { id: "wiki", href: "wiki.html", label: "Wiki" },
    { id: "ecosystem", href: "ecosystem.html", label: "Ecosystem" },
    { id: "api", href: "index.html", label: "API Explorer" }
  ];

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text) { node.textContent = text; }
    return node;
  }

  function addNavigation() {
    var nav = make("nav", "mk-global-nav");
    nav.setAttribute("aria-label", "Salyyy Minecraft Kit navigation");
    var brand = make("a", "mk-global-brand");
    brand.href = "wiki.html";
    var image = document.createElement("img");
    image.src = "assets/salyyy-minecraft-kit-logo.webp";
    image.alt = "";
    brand.append(image, document.createTextNode("Salyyy Minecraft Kit"));
    nav.append(brand);
    pages.forEach(function (item) {
      var link = make("a", "mk-global-link", item.label);
      link.href = item.href;
      if (item.id === page) { link.setAttribute("aria-current", "page"); }
      nav.append(link);
    });
    document.body.insertBefore(nav, document.body.firstElementChild);
  }

  function addIntro() {
    var config = {
      ecosystem: ["Ecosystem atlas", "Pinned sources, exact versions, and platform contracts."],
      api: ["RPG API explorer", "Search the deep, local symbol catalog without leaving the Kit wiki." ]
    }[page];
    if (!config) { return; }
    var main = document.querySelector("main");
    if (!main) { return; }
    var intro = make("section", "mk-page-intro");
    intro.append(make("p", "", config[0]), make("h1", "", config[1]));
    main.parentNode.insertBefore(intro, main);
  }

  function showLoader(firstVisit) {
    var loader = make("div", "mk-loader");
    if (!firstVisit) { loader.classList.add("is-quick"); }
    loader.setAttribute("role", "status");
    loader.setAttribute("aria-label", "Loading Salyyy Minecraft Kit");
    var mark = make("div", "mk-loader-mark");
    mark.append(make("div", "mk-loader-lines"));
    var image = document.createElement("img");
    image.src = "assets/salyyy-minecraft-kit-logo.webp";
    image.alt = "";
    mark.append(image, make("h1", "", "Minecraft Kit"), make("small", "", "by SalyVn"));
    loader.append(mark);
    document.body.append(loader);
    window.setTimeout(function () {
      loader.classList.add("is-leaving");
      window.setTimeout(function () { loader.remove(); }, 420);
    }, firstVisit ? 1420 : 360);
  }

  function addLoader() {
    var firstVisit = true;
    try {
      firstVisit = !window.localStorage.getItem("salyyy-minecraft-kit-loader-seen");
      if (firstVisit) { window.localStorage.setItem("salyyy-minecraft-kit-loader-seen", "1"); }
    } catch (error) {
      // Private browsing or file:// policies may deny storage; keep the loader functional.
      firstVisit = false;
    }
    showLoader(firstVisit);
  }

  function handleInternalLinks() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest("a[href]");
      if (!link || link.target || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
      var href = link.getAttribute("href");
      if (!href || !/^(?:wiki\.html|ecosystem\.html|index\.html)(?:$|[?#])/.test(href)) { return; }
      var target = new URL(link.href, window.location.href);
      if (target.pathname === window.location.pathname) { return; }
      event.preventDefault();
      document.documentElement.classList.add("mk-page-leaving");
      showLoader(false);
      window.setTimeout(function () { window.location.assign(target.href); }, 360);
    });
  }

  addNavigation();
  addIntro();
  addLoader();
  handleInternalLinks();
}());
