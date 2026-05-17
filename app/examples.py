"""
Random example question generator for the MovieGraph UI.
Edit the pools below to change what values get substituted into the templates.
"""

import random

# ─── Value pools (edit freely) ────────────────────────────────────────────────

MOVIES = [
    "The Godfather", "Inception", "The Dark Knight", "Pulp Fiction",
    "Schindler's List", "The Shawshank Redemption", "Forrest Gump",
    "The Matrix", "GoodFellas", "Fight Club", "Interstellar",
    "The Silence of the Lambs", "Parasite", "Spirited Away", "Whiplash",
    "The Martian", "La La Land", "Mad Max: Fury Road", "Her",
    "No Country for Old Men", "There Will Be Blood", "Arrival",
    "Blade Runner 2049", "Dunkirk", "The Grand Budapest Hotel",
]

PERSONS = [
    "Leonardo DiCaprio", "Meryl Streep", "Cate Blanchett", "Tom Hanks",
    "Denzel Washington", "Natalie Portman", "Joaquin Phoenix", "Viola Davis",
    "Brad Pitt", "Charlize Theron", "Ralph Fiennes", "Tilda Swinton",
    "Anthony Hopkins", "Frances McDormand", "Morgan Freeman",
    "Daniel Day-Lewis", "Judi Dench", "Gary Oldman",
]

DIRECTORS = [
    "Christopher Nolan", "Steven Spielberg", "Martin Scorsese",
    "Quentin Tarantino", "David Fincher", "Denis Villeneuve",
    "Alfonso Cuarón", "Bong Joon-ho", "Wes Anderson", "Paul Thomas Anderson",
    "Ridley Scott", "James Cameron", "David Lynch", "Stanley Kubrick",
]

ACTORS = [
    "Tom Hanks", "Leonardo DiCaprio", "Meryl Streep", "Morgan Freeman",
    "Cate Blanchett", "Brad Pitt", "Viola Davis", "Joaquin Phoenix",
    "Charlize Theron", "Natalie Portman", "Ryan Gosling", "Amy Adams",
]

STUDIOS = ["Pixar", "Studio Ghibli", "A24"]

GENRES = [
    "Thriller", "Comedy", "Science Fiction", "Drama", "Horror",
    "Action", "Romance", "Animation", "Crime",
    "Fantasy", "Mystery",
]

THEMES = ["time travel", "space exploration", "coming of age", "loss of a loved one", "prison escape"]

YEARS = [str(y) for y in range(2000, 2025)]
DECADES = [f"{decade}s" for decade in range(1960, 2025, 10)]

COUNTRIES = [
    "France", "Japan", "South Korea", "Italy", "Germany",
    "Spain", "Mexico", "India", "Denmark", "Sweden", "Iran", "Brazil",
]

USERS = ["sverlaan", "flrz", "liannehr"]

# ─── Question templates ────────────────────────────────────────────────────────

QUESTION_TEMPLATES = [
    "Overview of {MOVIE}",
    "Cast of {MOVIE}",
    "Crew of {MOVIE}",
    "Movies about {THEME}",
    "Top movies from {YEAR}",
    "Best {GENRE} movies from the {DECADE}",
    "Top movies from {COUNTRY}",
    "Top {GENRE} movies from {COUNTRY}",
    "Movies from {STUDIO}",
    "What actors acted in the most movies?",
    "Filmography of {PERSON}",
    "Who has collaborated with {PERSON} the most?",
    "Movies directed by {DIRECTOR} and star {ACTOR}",
    "Highest rated movies from {PERSON}",
    "Movies similar to {MOVIE}",
    "Movies from the same director as {MOVIE}",
    "Movies with shared cast with {MOVIE}",
    "Movies with similar Mini-Themes as {MOVIE}",
    "Watchlist of {USER}, sorted by release date",
    "Recommend {GENRE} movies to {USER}",
    "Five star rated movies by {USER}",
    "Worst rated movies by {USER}",
    "What movies similar to {MOVIE} has {USER} not seen yet?",
    "What movies that star {PERSON} has {USER} seen?",
    "What movies watched by {USER} would you recommend to {USER}?",
    "Movies in the watchlists of both {USER} and {USER}",
    "What 10 movies would you recommend to {USER} and {USER} together?",
    "Shortest path between {PERSON} and {PERSON}",
    "Shortest path between {MOVIE} and {MOVIE}",
]

# ─── Fill logic ────────────────────────────────────────────────────────────────


def _fill_template(template: str) -> str:
    result = template

    # Sample without replacement for placeholders that can appear multiple times
    for placeholder, pool in [
        ("{USER}", USERS),
        ("{PERSON}", PERSONS),
        ("{MOVIE}", MOVIES),
    ]:
        count = result.count(placeholder)
        if count:
            picked = random.sample(pool, min(count, len(pool)))
            for value in picked:
                result = result.replace(placeholder, value, 1)

    # Single-occurrence placeholders
    replacements = {
        "{DIRECTOR}": DIRECTORS,
        "{ACTOR}": ACTORS,
        "{GENRE}": GENRES,
        "{YEAR}": YEARS,
        "{COUNTRY}": COUNTRIES,
        "{DECADE}": DECADES,
        "{THEME}": THEMES,
        "{STUDIO}": STUDIOS,
    }
    for placeholder, pool in replacements.items():
        if placeholder in result:
            result = result.replace(placeholder, random.choice(pool))

    return result


def get_random_examples(n: int = 6) -> list[str]:
    """Return n randomly selected and filled example questions."""
    templates = random.sample(QUESTION_TEMPLATES, n)
    return [_fill_template(t) for t in templates]
