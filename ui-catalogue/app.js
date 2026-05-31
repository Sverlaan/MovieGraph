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
      if (i >= words.length) {
        answerEl.innerHTML = renderMarkdown(escHtml(text));
        resolve();
        return;
      }
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
    <div class="detail-info-section" id="detail-info-section" style="display:none"></div>
    <div id="detail-cast-section"       class="detail-extra-section" style="display:none"></div>
    <div id="detail-oscar-section"      class="detail-extra-section" style="display:none"></div>
    <div id="detail-collection-section" class="detail-extra-section" style="display:none"></div>
    <div id="detail-similar-section"    class="detail-extra-section" style="display:none"></div>`;

  if (movie.slug) {
    fetch(`/api/movie/${encodeURIComponent(movie.slug)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) fillMovieDetail(data); })
      .catch(() => {});

    fetch(`/api/movie/${encodeURIComponent(movie.slug)}/similar`)
      .then(r => r.ok ? r.json() : null)
      .then(similar => { if (similar && similar.length) fillSimilarMovies(similar); })
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

function infoRowClickable(label, items, queryFn) {
  if (!items || !items.length) return "";
  const chips = items
    .map(item => `<span class="detail-info-chip" data-query="${escHtml(queryFn(item))}">${escHtml(item)}</span>`)
    .join(" · ");
  return `<div class="detail-info-row">
    <span class="detail-info-label">${label}</span>
    <span class="detail-info-value">${chips}</span>
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

  // Info table
  const section = document.getElementById("detail-info-section");
  if (section) {
    section.innerHTML = `
      <div class="detail-info-left">
        ${infoRowClickable("Director",   (data.directors || []).map(d => typeof d === "string" ? d : d.name).filter(Boolean), name => `Movies directed by ${name}`)}
        ${infoRowClickable("Countries",  data.countries || [],                   country => `Movies from ${country}`)}
        ${infoRowClickable("Languages",  (data.languages || []).filter(Boolean), lang    => `Movies in ${lang}`)}
        ${infoRowClickable("Genres",     data.genres || [],                      genre   => `Movies in the ${genre} genre`)}
        ${infoRowClickable("Themes",     data.mini_themes || [],                 theme   => `Movies with mini-theme ${theme}`)}
      </div>`;
    section.addEventListener("click", e => {
      const chip = e.target.closest("[data-query]");
      if (!chip) return;
      inputEl.value = chip.dataset.query;
      submitQuestion();
    });
    section.style.display = "";
    section.classList.add("card-reveal");
  }

  // Cast & Crew banner row: directors first, then cast, then other crew
  const directors = (data.directors || []).filter(d => d && d.name).map(d => ({ ...d, _role: "director", _label: "Director" }));
  const castMembers = (data.cast || []).filter(c => c && c.name).map(c => ({ ...c, _role: "cast", _label: c.character || "Cast" }));
  const crewMembers = (data.crew || []).filter(c => c && c.name).map(c => ({ ...c, _role: "crew", _label: c.job || "Crew" }));
  const people = [...directors, ...castMembers, ...crewMembers];
  if (people.length) {
    const castSection = document.getElementById("detail-cast-section");
    if (castSection) {
      castSection.innerHTML = `
        <div class="detail-section-label">Cast & Crew</div>
        <div class="people-row">
          ${people.map(p => `
            <div class="person-banner-card" data-query="${escHtml(p._role === "director" ? `Movies directed by ${p.name}` : p._role === "crew" ? `Movies ${p.name} worked on` : `Movies starring ${p.name}`)}">
              ${p.avatar ? `<img class="person-banner-img" src="${escHtml(p.avatar)}" alt="${escHtml(p.name)}" onerror="this.style.display='none'" />` : ""}
              <div class="person-banner-info">
                <div class="person-banner-name">${escHtml(p.name)}</div>
                <div class="person-banner-role">${escHtml(p._label)}</div>
              </div>
            </div>`).join("")}
        </div>`;
      castSection.addEventListener("click", e => {
        const member = e.target.closest("[data-query]");
        if (!member) return;
        inputEl.value = member.dataset.query;
        submitQuestion();
      });
      castSection.style.display = "";
      castSection.classList.add("card-reveal");
    }
  }

  // Oscar nominations
  const oscarNoms = (data.oscar_noms || []).filter(o => o && o.category);
  if (oscarNoms.length) {
    const oscarSection = document.getElementById("detail-oscar-section");
    if (oscarSection) {
      const wins  = oscarNoms.filter(n => n.winner).length;
      const total = oscarNoms.length;
      const summary = wins > 0
        ? `${wins} win${wins > 1 ? "s" : ""} · ${total} nomination${total > 1 ? "s" : ""}`
        : `${total} nomination${total > 1 ? "s" : ""}`;
      oscarSection.innerHTML = `
        <div class="detail-section-label">Academy Awards</div>
        <div class="oscar-summary">${escHtml(summary)}</div>
        <div class="oscar-list">
          ${oscarNoms.map(n => `
            <div class="oscar-item${n.winner ? " oscar-winner" : ""}">
              <span>${n.winner ? "★" : "○"} ${escHtml(n.category || "")}</span>
              <span class="oscar-year">${escHtml(String(n.year || ""))}</span>
            </div>`).join("")}
        </div>`;
      oscarSection.style.display = "";
      oscarSection.classList.add("card-reveal");
    }
  }

  // Collection posters
  const collectionMovies = (data.collection_movies || []).filter(m => m && m.poster);
  if (data.collection_name && collectionMovies.length) {
    const colSection = document.getElementById("detail-collection-section");
    if (colSection) {
      const stack = collectionMovies.slice(0, 3);
      const collectionQuery = `Movies in the ${data.collection_name}`;
      colSection.innerHTML = `
        <div class="detail-section-label">${escHtml(data.collection_name)}</div>
        <div class="collection-stack">
          ${stack.map((m, i) => `
            <div class="collection-stack-item stack-pos-${i}">
              <img src="${escHtml(m.poster)}" alt="${escHtml(m.title || "")}" onerror="this.style.display='none'" />
            </div>`).join("")}
        </div>`;
      colSection.querySelector(".collection-stack").addEventListener("click", () => {
        inputEl.value = collectionQuery;
        submitQuestion();
      });
      colSection.style.display = "";
      colSection.classList.add("card-reveal");
    }
  }
}

function fillSimilarMovies(movies) {
  const section = document.getElementById("detail-similar-section");
  if (!section) return;
  section.innerHTML = `
    <div class="detail-section-label">Similar Movies</div>
    <div class="similar-movies-grid">
      ${movies.map(movie => `
        <div class="movie-banner-card" data-slug="${escHtml(movie.slug || "")}">
          ${movie.banner || movie.poster
            ? `<img class="banner-img" src="${escHtml(movie.banner || movie.poster)}" alt="" onerror="this.style.display='none'" />`
            : ""}
          <div class="banner-info">
            <div class="banner-title">${escHtml(movie.title || "—")}</div>
            ${movie.year ? `<div class="banner-year">${movie.year}</div>` : ""}
          </div>
        </div>`).join("")}
    </div>`;
  section.addEventListener("click", e => {
    const card = e.target.closest("[data-slug]");
    if (!card || !card.dataset.slug) return;
    const movie = movies.find(m => m.slug === card.dataset.slug);
    if (movie) renderMovieDetail(movie);
  });
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

function renderMarkdown(html) {
  return html
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,     "<em>$1</em>");
}
