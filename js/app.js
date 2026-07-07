// App shell: load data, route tabs, init view modules.
const App = { current: "finder", inited: {} };

App.show = function (view) {
  App.current = view;
  document.querySelectorAll("#tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view)
  );
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "view-" + view));

  if (view === "calculator" && !App.inited.calculator) { Calc.init(); App.inited.calculator = true; }
  if (view === "compare" && !App.inited.compare) { Compare.init(); App.inited.compare = true; }
  if (view === "compare") Compare.render();
  if (view === "explorer" && !App.inited.explorer) { Explorer.init(); App.inited.explorer = true; }
  if (view === "charts" && !App.inited.charts) { Charts.setup(); Charts.render(); App.inited.charts = true; }
  if (view === "about" && !App.inited.about) { App.renderAbout(); App.inited.about = true; }
  location.hash = view;
};

App.renderAbout = function () {
  const m = KS.meta;
  document.getElementById("about-content").innerHTML = `
    <h2>About this tool</h2>
    <p>An interactive explorer for New Zealand KiwiSaver funds, built from public data.
       It has three parts: a guided <b>fund finder</b>, a full <b>data explorer</b>, and a
       <b>chart builder</b> for slicing the data yourself.</p>
    <div class="pill-row">
      <span class="pill"><b>${m.counts.current_funds}</b> current funds</span>
      <span class="pill"><b>${m.counts.providers}</b> providers</span>
      <span class="pill"><b>${m.counts.funds_with_history}</b> with history</span>
      <span class="pill"><b>${m.counts.fma_records.toLocaleString()}</b> historical records</span>
      <span class="pill">history <b>${m.history_range.first}</b> → <b>${m.history_range.last}</b></span>
    </div>
    <h2>Data sources</h2>
    <ul>
      <li><b>Current snapshot:</b> ${m.sources.current}</li>
      <li><b>History:</b> ${m.sources.history}</li>
    </ul>
    <p class="muted">Every source is public. The FMA published consolidated quarterly
       KiwiSaver data as downloadable files until December 2022, then stopped; the current
       data now sits on the Companies Office Disclose Register behind a business API key.
       There is no single up-to-date file you can download that lists what every fund charges
       and how it has performed. This dataset rebuilds that picture from the records still reachable.</p>

    <h2>How the data was collated</h2>
    <ul>
      <li><b>The history</b> came from ${m.counts.fma_records.toLocaleString()} FMA quarterly
        records spanning ${m.history_range.first} to ${m.history_range.last}. The source files
        arrived in four different column layouts and several binary spreadsheet formats, which
        had to be converted and normalised into one consistent schema.</li>
      <li><b>The current list</b> of funds has no download button. It was collected by reading the
        Sorted Smart Investor search results page by page and extracting the structured data out
        of each page's raw HTML.</li>
      <li><b>Recent provider figures</b> and the industry reports are PDFs, from which tables were
        extracted programmatically and cleaned into rows.</li>
      <li><b>Joining it up</b> was the delicate part. Fund names are not unique (many providers each
        run a "Growth Fund" or "Balanced Fund"), so every fund is matched on its name plus its scheme
        to keep each track record tied to the right fund. Risk is shown as a band derived from each
        fund's standard type, and one internally impossible scraped row (a "Conservative" fund
        claiming a 22% one-year return) was filtered out.</li>
    </ul>

    <h2>Could you do this yourself?</h2>
    <p>Realistically, no. Not because any single step is exotic, but because it demands a stack of
       skills and a tolerance for tedium few people have all at once. To reproduce even the core of
       it you would need to know the FMA stopped publishing and where the data moved to, scrape a
       website that has no download button, convert and reconcile years of inconsistently formatted
       spreadsheets, pull clean tables out of PDFs, and, hardest of all, spot the silent traps: funds
       with identical names merging together, a risk figure attaching to the wrong fund, an impossible
       row sitting quietly in the results. A casual attempt does not fail loudly; it hands back a
       clean-looking, wrong answer.</p>
    <p>The practical outcome is that most people never do it. They stay in a default fund or pick on
       brand familiarity, because the honest cost of doing the research by hand is measured in days of
       specialist work. Doing that collection and cross-checking once, transparently, so the only part
       left is the choice that actually matters to you, is the whole reason this tool exists.</p>

    <h2>Known gaps &amp; caveats</h2>
    <ul>${m.known_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>
    <p class="muted">${m.license} Fund suitability guidance uses standard KiwiSaver
       risk categories (Defensive → Aggressive); it is educational only and not personalised
       financial advice. Always check a fund's current Product Disclosure Statement.</p>
    <p class="muted">Generated ${new Date(m.generated).toLocaleDateString("en-NZ")}.</p>
  `;
};

App.init = async function () {
  try {
    await KS.load();
  } catch (e) {
    document.getElementById("loading").textContent =
      "Could not load fund data. If viewing locally, serve over http (e.g. python3 -m http.server).";
    console.error(e);
    return;
  }
  if (window.Chart) Chart.defaults.animation = false;
  document.getElementById("loading").hidden = true;
  Finder.init();
  document.querySelectorAll("#tabs button").forEach((b) =>
    b.addEventListener("click", () => App.show(b.dataset.view))
  );
  // global handler for any "＋ Compare" / remove button across views
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cmp]");
    if (b) Compare.toggle(+b.dataset.cmp);
  });
  const views = ["finder", "calculator", "compare", "explorer", "charts", "about"];
  const start = location.hash.replace("#", "");
  App.show(views.includes(start) ? start : "finder");
};

document.addEventListener("DOMContentLoaded", App.init);
