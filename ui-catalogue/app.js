// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
const API_URL        = "/ask";
const AVATAR_FALLBACK = "https://via.placeholder.com/140x140?text=?";

let currentData = null;

// ─── DOM refs ─────────────────────────────────────────────
const inputEl        = document.getElementById("question-input");
const outputView     = document.getElementById("output-view");
const loadingEl      = document.getElementById("loading");
const answerEl       = document.getElementById("answer-text");
const dividerEl      = document.getElementById("results-divider");
const movieGridEl    = document.getElementById("movie-grid");
const personGridEl   = document.getElementById("person-grid");
const movieDetailEl  = document.getElementById("movie-detail");
const personDetailEl = document.getElementById("person-detail");

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
  loadingEl.style.display  = on ? "flex" : "none";
  if (on) {
    answerEl.style.display = "";
    answerEl.textContent = "";
    answerEl.classList.remove("styled");
    hideAll();
  }
}

function hideAll() {
  for (const el of [movieGridEl, personGridEl, movieDetailEl, personDetailEl]) {
    el.style.display = "none";
    el.style.visibility = "";
    el.classList.remove("card-reveal", "expanded");
    el.innerHTML = "";
  }
  dividerEl.style.display = "none";
  dividerEl.style.visibility = "";
}

// ═══════════════════════════════════════════════════════════
// MAIN RENDER DISPATCHER
// ═══════════════════════════════════════════════════════════
async function renderResponse(data) {
  const { answer, result_type, results } = data;

  const hasCards = ["movie_list","person_list"].includes(result_type);

  if (hasCards) {
    dividerEl.style.display = "block";
    if (result_type === "movie_list")  { renderMovieGrid(results);  movieGridEl.style.visibility    = "hidden"; }
    if (result_type === "person_list") { results.length === 1 ? renderPersonDetail(results[0]) : renderPersonGrid(results);
                                         personDetailEl.style.visibility = "hidden"; personGridEl.style.visibility = "hidden"; }
  }

  await showAnswer(answer);

  for (const el of [movieGridEl, personGridEl, personDetailEl]) {
    el.style.visibility = "";
    el.classList.add("card-reveal");
  }
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
// CARD RENDERERS
// ═══════════════════════════════════════════════════════════
const MOVIE_PRIMARY  = new Set(["title","year","poster","slug","banner","rating"]);
const PERSON_PRIMARY = new Set(["name","avatar","picture","person_slug"]);
const PERSON_DETAIL_PRIMARY = new Set(["name","avatar","picture","person_slug","biography"]);

function renderMovieGrid(results) {
  movieGridEl.innerHTML = "";
  movieGridEl.style.display = "grid";
  results.forEach(movie => {
    const card = document.createElement("div");
    card.className = "movie-banner-card";
    const imgSrc = movie.banner || movie.poster;
    card.innerHTML = `
      ${imgSrc
        ? `<img class="banner-img" src="${escHtml(imgSrc)}" alt="" onerror="this.style.display='none'" />`
        : ""}
      <div class="banner-info">
        <div class="banner-title">${escHtml(movie.title || "—")}</div>
        ${movie.year ? `<div class="banner-year">${movie.year}</div>` : ""}
      </div>`;
    card.addEventListener("click", () => {
      const saved = {
        answer:  answerEl.style.display,
        divider: dividerEl.style.display,
      };
      movieGridEl.style.display = "none";
      answerEl.style.display    = "none";
      dividerEl.style.display   = "none";
      window.scrollTo({ top: 0, behavior: "smooth" });
      renderMovieDetail(movie, () => {
        answerEl.style.display  = saved.answer;
        dividerEl.style.display = saved.divider;
      });
    });
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

function renderMovieDetail(movie, onBack = null) {
  movieDetailEl.style.display = "flex";
  movieDetailEl.classList.add("expanded");
  const year      = movie.year    ? ` (${movie.year})` : "";
  const rating    = movie.rating  ? `★ ${Number(movie.rating).toFixed(1)}` : "";
  const runtime   = movie.runtime ? `${movie.runtime} min` : "";
  const metaParts = [rating, runtime].filter(Boolean);
  movieDetailEl.innerHTML = `
    <div class="detail-hero">
      <div class="detail-banner-wrap">
        ${movie.banner ? `<img class="detail-banner" src="${escHtml(movie.banner)}" alt="" onerror="this.style.display='none'" />` : ""}
      </div>
      <button class="detail-back-btn" id="detail-back">← Back</button>
      <div class="detail-content">
        ${movie.poster ? `<img class="detail-poster" src="${escHtml(movie.poster)}" alt="${escHtml(movie.title || "")}" onerror="this.style.display='none'" />` : ""}
        <div class="detail-body" id="detail-overlay-body">
          <h2>${escHtml(movie.title || "—")}${escHtml(year)}</h2>
          ${metaParts.length ? `<div class="detail-meta">${metaParts.join(" · ")}</div>` : ""}
        </div>
      </div>
    </div>
    <div class="detail-info-section" id="detail-info-section" style="display:none"></div>`;

  if (movie.slug) {
    fetch(`/api/movie/${encodeURIComponent(movie.slug)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) fillMovieDetail(data); })
      .catch(() => {});
  }

  document.getElementById("detail-back").addEventListener("click", () => {
    movieDetailEl.style.display = "none";
    movieDetailEl.classList.remove("expanded");
    movieGridEl.style.display = "grid";
    if (onBack) onBack();
  });
}

function infoRow(label, value) {
  if (!value) return "";
  return `<div class="detail-info-row">
    <span class="detail-info-label">${label}</span>
    <span class="detail-info-value">${escHtml(value)}</span>
  </div>`;
}

function fillMovieDetail(data) {
  const body = document.getElementById("detail-overlay-body");
  if (body) {
    const yr      = data.year    ? ` (${data.year})` : "";
    const rating  = data.rating  ? `★ ${Number(data.rating).toFixed(1)}` : "";
    const runtime = data.runtime ? `${data.runtime} min` : "";
    const meta    = [rating, runtime].filter(Boolean).join(" · ");
    const lnks    = [];
    if (data.imdb_url)       lnks.push(`<a href="${escHtml(data.imdb_url)}" target="_blank">IMDb</a>`);
    if (data.letterboxd_url) lnks.push(`<a href="${escHtml(data.letterboxd_url)}" target="_blank">Letterboxd</a>`);
    body.innerHTML = `
      <h2>${escHtml(data.title || "—")}${escHtml(yr)}</h2>
      ${meta ? `<div class="detail-meta">${meta}</div>` : ""}
      ${data.tagline ? `<div style="font-style:italic;color:#aaa;font-size:.84rem">${escHtml(data.tagline)}</div>` : ""}
      ${data.plot    ? `<div class="detail-plot">${escHtml(data.plot)}</div>` : ""}
      ${lnks.length  ? `<div style="font-size:.8rem;margin-top:.5rem;color:#999">${lnks.join(" · ")}</div>` : ""}`;
  }

  const section = document.getElementById("detail-info-section");
  if (!section) return;

  const director   = (data.directors || []).join(", ") || null;
  const cast       = (data.cast || []).join(" · ") || null;
  const countries  = (data.countries || []).join(" · ") || null;
  const languages  = (data.languages || []).filter(Boolean).join(" · ") || null;
  const genres     = (data.genres || []).join(" · ") || null;
  const miniThemes = (data.mini_themes || []).join(" · ") || null;

  section.innerHTML = `
    <div class="detail-info-left">
      ${infoRow("Director",   director)}
      ${infoRow("Cast",       cast)}
      ${infoRow("Countries",  countries)}
      ${infoRow("Languages",  languages)}
      ${infoRow("Genres",     genres)}
      ${infoRow("Themes",     miniThemes)}
    </div>`;
  section.style.display = "";
  section.classList.add("card-reveal");
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
