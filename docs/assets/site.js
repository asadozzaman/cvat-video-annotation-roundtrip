(() => {
  const data = window.CVAT_DEMO;
  const github = "https://github.com/asadozzaman/cvat-video-annotation-roundtrip";
  const pages = [
    ["overview", "Overview", "index.html"],
    ["workflow", "Workflow", "workflow.html"],
    ["evidence", "Evidence", "evidence.html"],
    ["results", "Results", "results.html"],
    ["reproduce", "Reproduce", "reproduce.html"],
  ];
  const current = document.body.dataset.page;
  const header = document.getElementById("site-header");
  const footer = document.getElementById("site-footer");
  header.innerHTML = `<div class="site-header"><div class="container nav-shell">
    <a class="brand" href="index.html" aria-label="CVAT mini test home"><img src="assets/mark.svg" alt=""><span class="brand-copy"><strong>CVAT / ROUND TRIP</strong><small>ENGINEERING TEST</small></span></a>
    <nav class="nav-links" id="nav-links" aria-label="Main navigation">${pages.map(([id, label, href]) => `<a href="${href}"${id === current ? ' aria-current="page"' : ""}>${label}</a>`).join("")}</nav>
    <a class="header-action" href="${github}" target="_blank" rel="noopener noreferrer">View repository ↗</a>
    <button class="menu-toggle" id="menu-toggle" type="button" aria-label="Open navigation" aria-controls="nav-links" aria-expanded="false">☰</button>
  </div></div>`;
  footer.innerHTML = `<footer class="site-footer"><div class="container footer-inner"><span>CVAT Video Annotation API Mini Test · Verified on CVAT ${data.cvatVersion}</span><div class="footer-links"><a href="${github}" target="_blank" rel="noopener noreferrer">GitHub ↗</a><a href="${github}/blob/main/reports/CVAT_MINI_TEST_REPORT.md" target="_blank" rel="noopener noreferrer">Technical report ↗</a></div></div></footer>`;
  const menu = document.getElementById("menu-toggle");
  menu.addEventListener("click", () => {
    const open = menu.getAttribute("aria-expanded") !== "true";
    menu.setAttribute("aria-expanded", String(open));
    menu.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    document.getElementById("nav-links").classList.toggle("open", open);
  });
  document.querySelectorAll("[data-value]").forEach((node) => {
    const path = node.dataset.value.split(".");
    let value = data;
    for (const segment of path) value = value?.[segment];
    if (value !== undefined && value !== null) node.textContent = value;
  });
  document.querySelectorAll("[data-check-count]").forEach((node) => {
    node.textContent = Object.values(data.checks).filter(Boolean).length;
  });
  document.querySelectorAll("[data-repo-link]").forEach((node) => { node.href = github; });
  document.querySelectorAll("[data-report-link]").forEach((node) => { node.href = `${github}/blob/main/reports/CVAT_MINI_TEST_REPORT.md`; });

  const evidenceImage = document.getElementById("evidence-image");
  if (evidenceImage) {
    let frame = 10;
    let view = "annotated";
    const update = () => {
      const item = data.evidence.find((entry) => entry.frame === frame);
      evidenceImage.src = item[view];
      evidenceImage.alt = `${view === "annotated" ? "CVAT annotation on" : "Unannotated"} source video frame ${frame}`;
      document.getElementById("viewer-frame").textContent = `SOURCE FRAME / ${String(frame).padStart(3, "0")}`;
      document.getElementById("detail-frame").textContent = String(frame).padStart(3, "0");
      document.getElementById("detail-cvat-frame").textContent = item.mapping.cvat_api_frame;
      document.getElementById("detail-coordinates").textContent = item.points.join(", ");
      document.getElementById("detail-error").textContent = item.mapping.mean_squared_error.toFixed(4);
      document.querySelectorAll("[data-frame]").forEach((button) => button.setAttribute("aria-pressed", String(Number(button.dataset.frame) === frame)));
      document.querySelectorAll("[data-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.view === view)));
    };
    document.querySelectorAll("[data-frame]").forEach((button) => button.addEventListener("click", () => { frame = Number(button.dataset.frame); update(); }));
    document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => { view = button.dataset.view; update(); }));
    update();
  }

  const resultsGrid = document.getElementById("results-grid");
  if (resultsGrid) {
    const groupFor = (name) => {
      if (name.startsWith("VIDEO")) return "Video integrity";
      if (name.startsWith("SOURCE")) return "Source task";
      if (name.startsWith("EXPORT") || name.startsWith("EXPORTED")) return "CVAT export";
      if (name.startsWith("ROUND TRIP")) return "Round trip";
      return "Frame alignment";
    };
    const groups = new Map();
    for (const [name, pass] of Object.entries(data.checks)) {
      const group = groupFor(name);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push([name, pass]);
    }
    for (const group of ["Video integrity", "Source task", "CVAT export", "Round trip", "Frame alignment"]) {
      const checks = groups.get(group) || [];
      const article = document.createElement("article");
      article.className = "result-group";
      const heading = document.createElement("h3");
      heading.innerHTML = `<span></span><span>${checks.filter(([, pass]) => pass).length}/${checks.length}</span>`;
      heading.firstElementChild.textContent = group;
      article.append(heading);
      const list = document.createElement("ul");
      for (const [name, pass] of checks) {
        const row = document.createElement("li");
        const label = document.createElement("span");
        label.textContent = name.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
        const status = document.createElement("strong");
        status.textContent = pass ? "PASS" : "FAIL";
        if (!pass) status.style.color = "#ff8f86";
        row.append(label, status);
        list.append(row);
      }
      article.append(list);
      resultsGrid.append(article);
    }
  }

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const block = document.getElementById(button.dataset.copy);
      try {
        await navigator.clipboard.writeText(block.innerText.trim());
        button.textContent = "Copied";
        setTimeout(() => { button.textContent = "Copy"; }, 1600);
      } catch {
        button.textContent = "Select text";
      }
    });
  });
})();
