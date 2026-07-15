(function registerMinecraftKitAtlasRenderers(global) {
  "use strict";

  const numberFormatter = new Intl.NumberFormat("en-US");
  const dateFormatter = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit"
  });

  function text(value, fallback) {
    if (value === undefined || value === null || value === "") {
      return fallback === undefined ? "Not available" : fallback;
    }
    return String(value);
  }

  function number(value) {
    return numberFormatter.format(Number(value) || 0);
  }

  function date(value) {
    if (!value) {
      return "Not available";
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : dateFormatter.format(parsed);
  }

  function bytes(value) {
    const size = Number(value);
    if (!Number.isFinite(size) || size < 0) {
      return "Not available";
    }
    if (size < 1024) {
      return `${number(size)} B`;
    }
    if (size < 1024 * 1024) {
      return `${(size / 1024).toFixed(1)} KiB`;
    }
    return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
  }

  function createElement(tag, className, content) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (content !== undefined && content !== null) {
      node.textContent = String(content);
    }
    return node;
  }

  function externalLink(url, label) {
    let parsed;
    try {
      parsed = new URL(url);
    } catch (error) {
      parsed = null;
    }
    if (!parsed || parsed.protocol !== "https:") {
      return createElement("span", "unavailable-link", `${label}: unavailable`);
    }
    const link = createElement("a", "", label);
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  function definition(term, description) {
    const row = createElement("div");
    row.appendChild(createElement("dt", "", term));
    const value = createElement("dd");
    if (description instanceof Node) {
      value.appendChild(description);
    } else {
      value.textContent = text(description);
    }
    row.appendChild(value);
    return row;
  }

  function renderMetrics(elements, data) {
    elements.metricSourceCount.textContent = number(data.summary.sourceCount);
    elements.metricVersionCount.textContent = number(data.versions.versionCount);
    elements.metricDomainCount.textContent = number(data.domains.length);
  }

  function renderDomains(elements, data, selectDomain) {
    const fragment = document.createDocumentFragment();
    data.domains.forEach(function renderDomain(domain, index) {
      const button = createElement("button", "domain-card");
      button.type = "button";
      button.setAttribute("aria-label", `Open reviewed sources for ${domain.name}`);
      button.appendChild(createElement("span", "domain-card-index", String(index + 1).padStart(2, "0")));
      button.appendChild(createElement("h3", "", domain.name));
      button.appendChild(createElement("span", "domain-route", `/${domain.route}`));
      button.appendChild(createElement("p", "domain-card-keywords", domain.keywords.slice(0, 4).join(" / ")));
      const footer = createElement("span", "domain-card-footer");
      footer.appendChild(createElement("span", "", "Reviewed sources"));
      footer.appendChild(createElement("strong", "", number(data.summary.domainCounts[domain.id])));
      button.appendChild(footer);
      button.addEventListener("click", function openDomain() {
        selectDomain(domain.id);
      });
      fragment.appendChild(button);
    });
    elements.domainGrid.replaceChildren(fragment);
  }

  function renderProvenance(elements, data) {
    const provenance = data.provenance;
    const fragment = document.createDocumentFragment();
    fragment.appendChild(definition("GitHub snapshot", date(provenance.githubRetrievedAt)));
    fragment.appendChild(definition("Catalog SHA-256", provenance.githubCatalogSha256));
    fragment.appendChild(definition("Mojang manifest", date(provenance.minecraftRetrievedAt)));
    fragment.appendChild(definition("Manifest SHA-256", provenance.minecraftManifest.sha256));
    fragment.appendChild(definition("Capability inventory", date(data.releaseCapabilities.observedAt)));
    fragment.appendChild(definition("Capability SHA-256", provenance.releaseCapabilitiesSha256));
    fragment.appendChild(definition(
      "Official source",
      externalLink(provenance.minecraftManifest.url, "Open version manifest")
    ));
    elements.provenanceList.replaceChildren(fragment);
    elements.footerFreshness.textContent = `GitHub ${date(provenance.githubRetrievedAt)} / Mojang ${date(provenance.minecraftRetrievedAt)}`;
  }

  function renderDistribution(elements, data) {
    const entries = data.domains.map(function domainEntry(domain) {
      return [domain.name, Number(data.summary.domainCounts[domain.id]) || 0];
    });
    const maximum = Math.max(1, ...entries.map(function count(entry) { return entry[1]; }));
    const fragment = document.createDocumentFragment();
    entries.forEach(function renderEntry(entry) {
      const row = createElement("div", "distribution-row");
      row.appendChild(createElement("span", "", entry[0]));
      const track = createElement("span", "distribution-track");
      const value = createElement("span", "distribution-value");
      value.style.width = `${Math.max(3, (entry[1] / maximum) * 100)}%`;
      track.appendChild(value);
      row.appendChild(track);
      row.appendChild(createElement("span", "distribution-count", number(entry[1])));
      fragment.appendChild(row);
    });
    elements.distributionList.replaceChildren(fragment);
  }

  function renderOverview(elements, data, selectDomain) {
    renderMetrics(elements, data);
    renderDomains(elements, data, selectDomain);
    renderProvenance(elements, data);
    renderDistribution(elements, data);
  }

  function badge(label, className) {
    return createElement("span", `badge ${className || ""}`.trim(), label);
  }

  function sourceLicense(source) {
    const license = source.github.license;
    return license && license.spdx_id ? license.spdx_id : "not-declared";
  }

  function renderSourceCard(source) {
    const github = source.github;
    const head = github.default_branch_head;
    const release = github.latest_release;
    const article = createElement("article", "source-card");
    article.dataset.sourceId = source.id;

    const summary = createElement("div", "source-summary");
    const header = createElement("div", "source-card-head");
    const title = createElement("div");
    title.appendChild(createElement("h3", "", source.name));
    title.appendChild(createElement("p", "repository-name", source.repository));
    header.appendChild(title);
    const badges = createElement("div", "badge-row", "");
    badges.appendChild(badge(source.priority, "badge-priority"));
    badges.appendChild(badge(source.ingestion_policy, ""));
    badges.appendChild(badge(
      github.archived ? "Archived" : "Current",
      github.archived ? "badge-archived" : "badge-current"
    ));
    header.appendChild(badges);
    summary.appendChild(header);
    summary.appendChild(createElement("p", "source-rationale", source.rationale));
    const tags = createElement("div", "domain-tags");
    source.domains.forEach(function renderTag(domain) {
      tags.appendChild(createElement("span", "domain-tag", `/mc:${domain}`));
    });
    summary.appendChild(tags);

    const meta = createElement("div", "source-meta");
    const details = createElement("dl");
    details.appendChild(definition("License", sourceLicense(source)));
    details.appendChild(definition("Default branch", github.default_branch));
    details.appendChild(definition("Pinned revision", head.sha));
    details.appendChild(definition("Head committed", date(head.committed_at)));
    details.appendChild(definition("Repository push", date(github.pushed_at)));
    details.appendChild(definition("Popularity", `${number(github.stars)} stars / ${number(github.forks)} forks`));
    details.appendChild(definition("Latest release", release ? `${release.tag} / ${date(release.published_at)}` : "No tagged GitHub release"));
    meta.appendChild(details);
    const links = createElement("div", "source-links");
    links.appendChild(externalLink(github.url, "Source repository"));
    links.appendChild(externalLink(source.docs_url, "Documentation"));
    links.appendChild(externalLink(head.url, "Pinned revision"));
    if (release) {
      links.appendChild(externalLink(release.url, `Release ${release.tag}`));
    }
    meta.appendChild(links);

    article.appendChild(summary);
    article.appendChild(meta);
    return article;
  }

  function renderSources(elements, sources) {
    const fragment = document.createDocumentFragment();
    sources.forEach(function renderSource(source) {
      fragment.appendChild(renderSourceCard(source));
    });
    elements.sourceList.replaceChildren(fragment);
    elements.sourceList.setAttribute("aria-busy", "false");
    elements.sourceEmpty.hidden = sources.length !== 0;
  }

  function renderVersionMetrics(elements, data) {
    const counts = data.versions.countsByType;
    const entries = [
      ["All versions", data.versions.versionCount],
      ["Releases", counts.release],
      ["Snapshots", counts.snapshot],
      ["Old alpha", counts.old_alpha],
      ["Old beta", counts.old_beta]
    ];
    const fragment = document.createDocumentFragment();
    entries.forEach(function renderMetric(entry) {
      const cell = createElement("div", "version-metric");
      cell.appendChild(createElement("dt", "", entry[0]));
      cell.appendChild(createElement("dd", "", number(entry[1])));
      fragment.appendChild(cell);
    });
    elements.versionMetrics.replaceChildren(fragment);
  }

  function packVersion(pack) {
    return pack ? `${text(pack.major)}.${text(pack.minor)}` : "Not available";
  }

  function hydratedDefinitionList(detail, capability) {
    const definitions = createElement("dl", "latest-detail-grid");
    const client = detail.downloads && detail.downloads.client ? detail.downloads.client : {};
    const server = detail.downloads && detail.downloads.server ? detail.downloads.server : {};
    const javaVersion = detail.java_version || {};
    const assetIndex = detail.asset_index || {};
    const entries = [
      ["Release time", date(detail.release_time)],
      ["Java runtime", `${text(javaVersion.component)} / Java ${text(javaVersion.major_version)}`],
      ["Launcher minimum", text(detail.minimum_launcher_version)],
      ["Asset index", `${text(assetIndex.id)} / ${text(assetIndex.sha1)}`],
      ["Client artifact", `${bytes(client.size)} / ${text(client.sha1)}`],
      ["Server artifact", `${bytes(server.size)} / ${text(server.sha1)}`]
    ];
    if (capability) {
      entries.splice(2, 0,
        ["Protocol", capability.protocol],
        ["Resource pack", packVersion(capability.resource_pack)],
        ["Data pack", packVersion(capability.data_pack)]
      );
    }
    entries.forEach(function renderEntry(entry) {
      definitions.appendChild(definition(entry[0], entry[1]));
    });
    return definitions;
  }

  function renderLatestVersions(elements, data) {
    const fragment = document.createDocumentFragment();
    ["release", "snapshot"].forEach(function renderLatest(versionType) {
      const id = data.versions.latest[versionType];
      const detail = data.versions.details[id];
      const capability = data.releaseCapabilities.releases.find(function findCapability(item) {
        return item.id === id;
      });
      const manifestRecord = data.versions.history.find(function findRecord(record) {
        return record.id === id;
      });
      const card = createElement("article", "latest-card");
      card.appendChild(createElement("p", "latest-card-label", `Latest ${versionType}`));
      card.appendChild(createElement("h3", "", id));
      card.appendChild(hydratedDefinitionList(detail, capability));
      const links = createElement("div", "source-links");
      if (manifestRecord) {
        links.appendChild(externalLink(manifestRecord.url, "Version manifest record"));
      }
      card.appendChild(links);
      fragment.appendChild(card);
    });
    elements.latestVersions.replaceChildren(fragment);
  }

  function capabilityMetric(term, value) {
    const cell = createElement("div", "capability-metric");
    cell.appendChild(createElement("dt", "", term));
    cell.appendChild(createElement("dd", "", value));
    return cell;
  }

  function tagList(title, values) {
    const group = createElement("div", "capability-tag-group");
    group.appendChild(createElement("h4", "", title));
    const tags = createElement("div", "domain-tags");
    values.forEach(function renderTag(value) {
      tags.appendChild(createElement("code", "domain-tag", value));
    });
    group.appendChild(tags);
    return group;
  }

  function renderCapabilityProfile(elements, data) {
    const releaseId = data.versions.latest.release;
    const capability = data.releaseCapabilities.releases.find(function findLatest(item) {
      return item.id === releaseId;
    });
    if (!capability) {
      elements.releaseCapabilityProfile.hidden = true;
      return;
    }
    const inventory = capability.vanilla_inventory;
    const heading = createElement("div", "capability-heading");
    const title = createElement("div");
    title.appendChild(createElement("p", "eyebrow", "Verified client artifact inventory"));
    const headingText = createElement("h3", "", `Minecraft ${capability.id} capability profile`);
    headingText.id = "capability-profile-title";
    title.appendChild(headingText);
    heading.appendChild(title);
    heading.appendChild(createElement(
      "p",
      "capability-summary",
      "Exact version gates and vanilla surface counts observed without redistributing game code or assets."
    ));

    const metrics = createElement("dl", "capability-grid");
    [
      ["Protocol", capability.protocol],
      ["Java", capability.java_major],
      ["Resource pack", packVersion(capability.resource_pack)],
      ["Data pack", packVersion(capability.data_pack)],
      ["Core shaders", inventory.core_shader_files],
      ["Shader includes", inventory.include_shader_files],
      ["Post shaders", inventory.post_shader_files],
      ["Item geometry", inventory.item_geometry_entries],
      ["Item definitions", inventory.item_definition_entries],
      ["Font JSON", inventory.built_in_font_json_files]
    ].forEach(function addMetric(entry) {
      const value = typeof entry[1] === "number" ? number(entry[1]) : entry[1];
      metrics.appendChild(capabilityMetric(entry[0], value));
    });

    const detailGrid = createElement("div", "capability-detail-grid");
    const lists = createElement("div", "capability-lists");
    lists.appendChild(tagList("Built-in dialog IDs", inventory.built_in_dialog_ids));
    lists.appendChild(tagList("Observed font provider kinds", inventory.observed_font_provider_kinds));
    detailGrid.appendChild(lists);
    const provenance = createElement("dl", "capability-provenance");
    provenance.appendChild(definition("Evidence class", capability.evidence_class));
    provenance.appendChild(definition("Client SHA-1", capability.client_sha1));
    provenance.appendChild(definition("Observed", date(data.releaseCapabilities.observedAt)));
    provenance.appendChild(definition("Capability SHA-256", data.provenance.releaseCapabilitiesSha256));
    provenance.appendChild(definition("Method", capability.provenance.method));
    provenance.appendChild(definition("Release policy", capability.provenance.restrictions));
    provenance.appendChild(definition(
      "Version evidence",
      externalLink(capability.provenance.version_metadata_url, "Open version metadata")
    ));
    detailGrid.appendChild(provenance);

    elements.releaseCapabilityProfile.hidden = false;
    elements.releaseCapabilityProfile.replaceChildren(heading, metrics, detailGrid);
  }

  function renderVersions(elements, data) {
    renderVersionMetrics(elements, data);
    renderLatestVersions(elements, data);
    renderCapabilityProfile(elements, data);
  }

  function versionTypeLabel(value) {
    return {
      release: "Release",
      snapshot: "Snapshot",
      old_alpha: "Old alpha",
      old_beta: "Old beta"
    }[value] || value;
  }

  function renderVersionHistory(elements, versions, limit) {
    const visible = versions.slice(0, limit);
    const fragment = document.createDocumentFragment();
    visible.forEach(function renderVersion(version) {
      const row = createElement("tr");
      const versionCell = createElement("td");
      versionCell.appendChild(externalLink(version.url, version.id));
      row.appendChild(versionCell);
      row.appendChild(createElement("td", "", versionTypeLabel(version.type)));
      row.appendChild(createElement("td", "", date(version.release_time)));
      row.appendChild(createElement("td", "", text(version.compliance_level)));
      row.appendChild(createElement("td", "", version.sha1));
      fragment.appendChild(row);
    });
    elements.versionHistoryBody.replaceChildren(fragment);
    elements.versionResultCount.textContent = `Showing ${number(visible.length)} of ${number(versions.length)} matching versions.`;
    elements.loadMoreVersions.hidden = visible.length >= versions.length;
  }

  global.MinecraftKitAtlasRenderers = Object.freeze({
    createElement,
    renderOverview,
    renderSources,
    renderVersions,
    renderVersionHistory,
    sourceLicense,
    number,
    date
  });
}(window));
