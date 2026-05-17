// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
const API_URL        = "/ask";
const AVATAR_FALLBACK = "https://via.placeholder.com/140x140?text=?";

let currentData   = null;
let zoomBehaviour = null;
let svgSelection  = null;

// ─── DOM refs ─────────────────────────────────────────────
const inputEl        = document.getElementById("question-input");
const outputView     = document.getElementById("output-view");
const graphView      = document.getElementById("graph-view");
const viewToggle     = document.getElementById("view-toggle");
const btnOutput      = document.getElementById("btn-output");
const btnGraph       = document.getElementById("btn-graph");
const loadingEl      = document.getElementById("loading");
const answerEl       = document.getElementById("answer-text");
const queryTagsEl    = document.getElementById("query-tags");
const dividerEl      = document.getElementById("results-divider");
const movieGridEl    = document.getElementById("movie-grid");
const personGridEl   = document.getElementById("person-grid");
const movieDetailEl  = document.getElementById("movie-detail");
const personDetailEl = document.getElementById("person-detail");
const cypherCode     = document.getElementById("cypher-code");

// ═══════════════════════════════════════════════════════════
// INPUT & EXAMPLES
// ═══════════════════════════════════════════════════════════
inputEl.addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); submitQuestion(); }
});

async function loadExamples() {
  try {
    const res = await fetch("/api/examples");
    const questions = await res.json();
    const container = document.getElementById("examples");
    container.innerHTML = "";
    questions.forEach(q => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "example-chip";
      chip.textContent = q;
      chip.addEventListener("click", () => { inputEl.value = q; submitQuestion(); });
      container.appendChild(chip);
    });
  } catch (e) {
    console.warn("Could not load example questions", e);
  }
}
loadExamples();

// ═══════════════════════════════════════════════════════════
// VIEW TOGGLE
// ═══════════════════════════════════════════════════════════
btnOutput.addEventListener("click", () => showView("output"));
btnGraph.addEventListener("click",  () => showView("graph"));

function showView(view) {
  btnOutput.classList.toggle("active", view === "output");
  btnGraph.classList.toggle("active",  view === "graph");
  outputView.style.display = view === "output" ? "flex" : "none";
  graphView.style.display  = view === "graph"  ? "flex" : "none";
}

// ═══════════════════════════════════════════════════════════
// SUBMIT
// ═══════════════════════════════════════════════════════════
async function submitQuestion() {
  const question = inputEl.value.trim();
  if (!question) return;
  setLoading(true);
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    currentData = await res.json();
    setLoading(false);
    await renderResponse(currentData);
  } catch (err) {
    setLoading(false);
    showAnswer(`Something went wrong: ${err.message}`);
    outputView.style.display = "flex";
  }
}

// ═══════════════════════════════════════════════════════════
// LOADING STATE
// ═══════════════════════════════════════════════════════════
function setLoading(on) {
  outputView.style.display = "flex";
  graphView.style.display  = "none";
  viewToggle.style.display = "none";
  loadingEl.style.display  = on ? "flex" : "none";
  if (on) {
    answerEl.textContent = "";
    answerEl.classList.remove("styled");
    hideAll();
  }
}

function hideAll() {
  for (const el of [movieGridEl, personGridEl, movieDetailEl, personDetailEl]) {
    el.style.display = "none";
    el.innerHTML = "";
  }
  queryTagsEl.innerHTML = "";
  dividerEl.style.display = "none";
  cypherCode.innerHTML = "";
}

// ═══════════════════════════════════════════════════════════
// MAIN RENDER DISPATCHER
// ═══════════════════════════════════════════════════════════
async function renderResponse(data) {
  const { answer, result_type, results, graph, cypher, query_tags } = data;

  showView("output");
  await showAnswer(answer);

  if (query_tags && query_tags.length > 0) renderQueryTags(query_tags);

  const hasCards = ["movie_list","person_list","movie_detail"].includes(result_type);
  const hasGraph = graph && graph.nodes && graph.nodes.length > 0;

  if (hasCards) {
    dividerEl.style.display = "block";
    if (result_type === "movie_list")   renderMovieGrid(results);
    if (result_type === "person_list")  results.length === 1 ? renderPersonDetail(results[0]) : renderPersonGrid(results);
    if (result_type === "movie_detail") renderMovieDetail(results[0]);
  }

  if (hasGraph) renderGraph(graph);
  if (cypher)   cypherCode.innerHTML = highlightCypher(escHtml(cypher));

  if (hasGraph || cypher) viewToggle.style.display = "flex";
}

// ═══════════════════════════════════════════════════════════
// ANSWER ANIMATION
// ═══════════════════════════════════════════════════════════
function showAnswer(text) {
  return new Promise(resolve => {
    answerEl.textContent = "";
    answerEl.classList.add("styled");
    const words = text.split(/(\s+)/);
    let i = 0;
    function next() {
      if (i >= words.length) { resolve(); return; }
      answerEl.textContent += words[i++];
      setTimeout(next, 18);
    }
    next();
  });
}

// ═══════════════════════════════════════════════════════════
// QUERY TAGS
// ═══════════════════════════════════════════════════════════
function renderQueryTags(tags) {
  queryTagsEl.innerHTML = "";
  tags.forEach(({ label, value }) => {
    const color = LABEL_COLOR[label] || COLOR_DEFAULT;
    const span = document.createElement("span");
    span.className = "query-tag";
    span.textContent = value;
    span.style.borderColor = color + "66";
    span.style.backgroundColor = color + "14";
    span.style.color = color;
    queryTagsEl.appendChild(span);
  });
}

// ═══════════════════════════════════════════════════════════
// CARD RENDERERS
// ═══════════════════════════════════════════════════════════
const MOVIE_PRIMARY  = new Set(["title","year","poster","slug","banner","rating"]);
const PERSON_PRIMARY = new Set(["name","avatar","picture","person_slug"]);
const PERSON_DETAIL_PRIMARY = new Set(["name","avatar","picture","person_slug","biography"]);
const MOVIE_DETAIL_PRIMARY  = new Set([
  "title","year","poster","slug","rating","runtime","plot","tagline",
  "banner","trailer","imdb_url","letterboxd_url","tmdb_url"
]);

function renderMovieGrid(results) {
  movieGridEl.innerHTML = "";
  movieGridEl.style.display = "grid";
  results.forEach(movie => {
    const card = document.createElement("div");
    card.className = "movie-banner-card";
    const imgSrc = movie.banner || movie.poster;
    const extra = extraFields(movie, MOVIE_PRIMARY)
      .filter(f => typeof f.value !== "object")
      .slice(0, 2);
    card.innerHTML = `
      ${imgSrc
        ? `<img class="banner-img" src="${escHtml(imgSrc)}" alt="" onerror="this.style.display='none'" />`
        : ""}
      <div class="banner-info">
        <div class="banner-title">${escHtml(movie.title || "—")}</div>
        ${movie.year ? `<div class="banner-year">${movie.year}</div>` : ""}
        ${extra.length ? `<div class="banner-meta">${extra.map(f => escHtml(String(f.value))).join("  ·  ")}</div>` : ""}
      </div>`;
    movieGridEl.appendChild(card);
  });
}

function renderPersonGrid(results) {
  personGridEl.innerHTML = "";
  personGridEl.style.display = "grid";
  results.forEach(person => {
    const imgSrc = person.avatar || person.picture || AVATAR_FALLBACK;
    const card = document.createElement("div");
    card.className = "person-card";
    const extra = extraFields(person, PERSON_PRIMARY).slice(0, 2);
    card.innerHTML = `
      <div class="avatar-wrap">
        <img class="avatar" src="${imgSrc}" alt="${escHtml(person.name || "")}" onerror="this.src='${AVATAR_FALLBACK}'" />
      </div>
      <div class="person-name">${escHtml(person.name || "—")}</div>
      ${extra.length ? `<div class="person-meta">${extra.map(f => escHtml(String(f.value))).join(" · ")}</div>` : ""}`;
    personGridEl.appendChild(card);
  });
}

function renderPersonDetail(person) {
  personDetailEl.style.display = "flex";
  const imgSrc = person.avatar || person.picture || AVATAR_FALLBACK;
  const extra  = extraFields(person, PERSON_DETAIL_PRIMARY);
  const links  = person.url ? [`<a href="${person.url}" target="_blank">Profile</a>`] : [];
  personDetailEl.innerHTML = `
    <div class="detail-avatar-wrap">
      <img class="detail-avatar" src="${imgSrc}" alt="${escHtml(person.name || "")}" onerror="this.src='${AVATAR_FALLBACK}'" />
    </div>
    <div class="detail-body">
      <h2>${escHtml(person.name || "—")}</h2>
      ${extra.length ? `<div class="detail-meta">${extra.map(f => escHtml(String(f.value))).join(" · ")}</div>` : ""}
      ${person.biography ? `<div class="detail-plot">${escHtml(person.biography)}</div>` : ""}
      ${links.length    ? `<div style="font-size:.8rem;margin-top:.5rem">${links.join(" · ")}</div>` : ""}
    </div>`;
}

const TAG_TYPE_CLASS = {
  genres:      "genre",
  mini_themes: "minitheme",
  miniThemes:  "minitheme",
  themes:      "theme",
  studios:     "studio",
  countries:   "country",
  languages:   "language",
  collection:  "collection",
  collections: "collection",
  keywords:    "keyword",
  oscar_noms:  "oscarnom",
};

function renderMovieDetail(movie) {
  movieDetailEl.style.display = "flex";
  const year      = movie.year    ? ` (${movie.year})` : "";
  const rating    = movie.rating  ? `★ ${Number(movie.rating).toFixed(1)}` : "";
  const runtime   = movie.runtime ? `${movie.runtime} min` : "";
  const metaParts = [rating, runtime].filter(Boolean);
  const tags = Object.entries(movie)
    .filter(([, v]) => Array.isArray(v))
    .flatMap(([k, v]) => v
      .map(t => (t && typeof t === "object") ? (t.name || t.title || Object.values(t)[0]) : t)
      .filter(t => t !== null && t !== undefined && String(t) !== "[object Object]")
      .map(t => ({ text: String(t), cls: TAG_TYPE_CLASS[k] || "" }))
    )
    .slice(0, 14);
  const links = [];
  if (movie.imdb_url)       links.push(`<a href="${movie.imdb_url}" target="_blank">IMDb</a>`);
  if (movie.letterboxd_url) links.push(`<a href="${movie.letterboxd_url}" target="_blank">Letterboxd</a>`);
  movieDetailEl.innerHTML = `
    <div class="detail-banner-wrap">
      ${movie.banner ? `<img class="detail-banner" src="${escHtml(movie.banner)}" alt="" onerror="this.style.display='none'" />` : ""}
    </div>
    <div class="detail-content">
      ${movie.poster ? `<img class="detail-poster" src="${escHtml(movie.poster)}" alt="${escHtml(movie.title || "")}" onerror="this.style.display='none'" />` : ""}
      <div class="detail-body">
        <h2>${escHtml(movie.title || "—")}${escHtml(year)}</h2>
        ${metaParts.length ? `<div class="detail-meta">${metaParts.join(" · ")}</div>` : ""}
        ${movie.tagline ? `<div style="font-style:italic;color:#777;font-size:.84rem">${escHtml(movie.tagline)}</div>` : ""}
        ${movie.plot    ? `<div class="detail-plot">${escHtml(movie.plot)}</div>` : ""}
        ${links.length  ? `<div style="font-size:.8rem;margin-top:.5rem;color:#999">${links.join(" · ")}</div>` : ""}
      </div>
    </div>
    ${tags.length ? `<div class="detail-tags">${tags.map(({text}) => `<span class="detail-tag">${escHtml(text)}</span>`).join("")}</div>` : ""}`;
}

// ═══════════════════════════════════════════════════════════
// GRAPH RENDERER (D3 v7 — monochrome palette)
// ═══════════════════════════════════════════════════════════
const LABEL_COLOR = {
  Movie:      "#2a2a2a",
  Person:     "#555",
  Genre:      "#777",
  Theme:      "#666",
  MiniTheme:  "#888",
  User:       "#444",
  Studio:     "#999",
  Country:    "#aaa",
  Language:   "#bbb",
  Collection: "#333",
  Keyword:    "#888",
  OscarNom:   "#666",
};
const COLOR_DEFAULT = "#999";

function labelColor(labels) {
  for (const l of (labels || [])) if (LABEL_COLOR[l]) return LABEL_COLOR[l];
  return COLOR_DEFAULT;
}

function nodeDisplayName(n) {
  const p = n.properties || {};
  const raw = p.title || p.name || p.username || p.display_name || (n.labels || [])[0] || "?";
  return raw.length > 18 ? raw.slice(0, 16) + "…" : raw;
}

function renderGraph(graphData) {
  const container = document.getElementById("graph-container");
  d3.select(container).select("svg").remove();

  if (!graphData || !graphData.nodes.length) {
    document.getElementById("graph-legend").innerHTML =
      `<span style="color:#aaa;font-size:.7rem;letter-spacing:.08em">NO GRAPH DATA</span>`;
    return;
  }

  const W = container.clientWidth;
  const H = container.clientHeight;

  const nodes = graphData.nodes.map(n => ({ ...n }));
  const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]));
  const edges = graphData.edges
    .filter(e => nodeById[e.source] && nodeById[e.target])
    .map(e => ({ ...e }));

  const presentLabels = [...new Set(nodes.flatMap(n => n.labels || []))];
  document.getElementById("graph-legend").innerHTML =
    presentLabels.map(l =>
      `<div><span class="legend-dot" style="background:${LABEL_COLOR[l] || COLOR_DEFAULT}"></span>${l}</div>`
    ).join("");

  const svg = d3.select(container).insert("svg", ":first-child")
    .attr("width", "100%").attr("height", "100%");

  svg.append("defs").append("marker")
    .attr("id", "arrow-cat")
    .attr("viewBox", "0 -4 8 8").attr("refX", 24).attr("refY", 0)
    .attr("markerWidth", 5).attr("markerHeight", 5).attr("orient", "auto")
    .append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", "#ccc");

  const g = svg.append("g");
  zoomBehaviour = d3.zoom().scaleExtent([0.2, 5]).on("zoom", e => g.attr("transform", e.transform));
  svg.call(zoomBehaviour);
  svgSelection = svg;

  const sim = d3.forceSimulation(nodes)
    .force("link",      d3.forceLink(edges).id(d => d.id).distance(110))
    .force("charge",    d3.forceManyBody().strength(-280))
    .force("center",    d3.forceCenter(W / 2, H / 2))
    .force("collision", d3.forceCollide(30));

  const link = g.append("g").attr("fill", "none")
    .selectAll("line").data(edges).join("line")
    .attr("stroke", "#ddd").attr("stroke-width", 1)
    .attr("marker-end", "url(#arrow-cat)");

  const edgeLabel = g.append("g")
    .selectAll("text").data(edges).join("text")
    .attr("text-anchor", "middle")
    .attr("font-size", "9px")
    .attr("fill", "#ccc")
    .attr("font-family", "'Space Grotesk', sans-serif")
    .attr("letter-spacing", "0.04em")
    .text(d => d.type || "");

  const node = g.append("g")
    .selectAll("g").data(nodes).join("g")
    .style("cursor", "grab")
    .call(d3.drag()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag",  (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end",   (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    );

  node.append("circle")
    .attr("r", 18)
    .attr("fill", d => labelColor(d.labels))
    .attr("stroke", "#fff").attr("stroke-width", 2);

  node.append("text")
    .attr("text-anchor", "middle").attr("dy", "31px")
    .attr("font-size", "10px").attr("font-weight", "500")
    .attr("font-family", "'Space Grotesk', sans-serif")
    .attr("fill", "#444")
    .text(d => nodeDisplayName(d));

  node.append("title").text(d => {
    const p = d.properties || {};
    return `[${(d.labels||[]).join(",")}] ${p.title || p.name || p.username || "?"}`;
  });

  sim.on("tick", () => {
    link
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    edgeLabel
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2);
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });
}

document.getElementById("btn-zoom-in").addEventListener("click", () => {
  if (svgSelection && zoomBehaviour)
    svgSelection.transition().duration(250).call(zoomBehaviour.scaleBy, 1.4);
});
document.getElementById("btn-zoom-out").addEventListener("click", () => {
  if (svgSelection && zoomBehaviour)
    svgSelection.transition().duration(250).call(zoomBehaviour.scaleBy, 0.7);
});
document.getElementById("btn-zoom-fit").addEventListener("click", () => {
  if (svgSelection && zoomBehaviour)
    svgSelection.transition().duration(350).call(zoomBehaviour.transform, d3.zoomIdentity);
});

// ═══════════════════════════════════════════════════════════
// CYPHER SYNTAX HIGHLIGHTING
// ═══════════════════════════════════════════════════════════
const CYPHER_KEYWORDS = /\b(MATCH|OPTIONAL\s+MATCH|WHERE|RETURN|WITH|ORDER\s+BY|LIMIT|SKIP|CREATE|MERGE|SET|DELETE|DETACH\s+DELETE|REMOVE|CALL|YIELD|AS|AND|OR|NOT|IN|DISTINCT|COLLECT|COUNT|SUM|EXISTS|CASE|WHEN|THEN|ELSE|END|NULL|TRUE|FALSE|IS\s+NULL|IS\s+NOT\s+NULL|UNWIND|UNION|ALL)\b/gi;
const CYPHER_LABELS   = /(:[\w]+)/g;
const CYPHER_STRINGS  = /("[^"]*"|'[^']*')/g;

function highlightCypher(code) {
  return code
    .replace(CYPHER_STRINGS,  m => `<span class="cypher-str">${m}</span>`)
    .replace(CYPHER_LABELS,   m => `<span class="cypher-lbl">${m}</span>`)
    .replace(CYPHER_KEYWORDS, m => `<span class="cypher-kw">${m}</span>`);
}

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════
function extraFields(obj, primarySet) {
  return Object.entries(obj)
    .filter(([k, v]) => !primarySet.has(k) && v !== null && v !== undefined && v !== "")
    .filter(([, v]) => typeof v !== "object")
    .map(([k, v]) => ({ key: k, value: v }));
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
