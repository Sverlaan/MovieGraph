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

GENRES = [
    "Thriller", "Comedy", "Science Fiction", "Drama", "Horror",
    "Action", "Romance", "Animation", "Crime",
    "Fantasy", "Mystery",
]

YEARS = [str(y) for y in range(2000, 2025)]
DECADES = [f"{decade}s" for decade in range(1960, 2025, 10)]

COUNTRIES = [
    "France", "Japan", "South Korea", "Italy", "Germany",
    "Spain", "Mexico", "India", "Denmark", "Sweden", "Iran", "Brazil",
]

USERS = ["sverlaan", "flrz", "liannehr"]

# ─── Question templates ────────────────────────────────────────────────────────

QUESTION_TEMPLATES = [
    "Give me an overview of the movie {MOVIE}",
    "What is the cast of {MOVIE}?",
    "What is the crew of {MOVIE}?",
    "What are the highest rated movies from {YEAR}?",
    "What are the highest rated {GENRE} movies from the {DECADE}?",
    "What are the highest rated movies from {COUNTRY}?",
    "What are the highest rated {GENRE} movies from {COUNTRY}?",
    "Show me all movies from Studio Ghibli",
    "What actors acted in the most movies?",
    "Show me the full filmography of {PERSON}",
    "Who has collaborated with {PERSON}, sorted by the number of collaborations",
    "What movies are directed by {DIRECTOR} and star {ACTOR}?",
    "What are the five highest rated movies from {PERSON}?",
    "What movies are similar to {MOVIE}?",
    "What movies are from the same director as {MOVIE}?",
    "What movies have a shared cast (min two people) with {MOVIE} and who are they?",
    "What movies have most similar Mini-Themes to {MOVIE} and what are they?",
    "Show me the watchlist of {USER}, sorted by release date",
    "What {GENRE} movies would you recommend to {USER}?",
    "Show the 5 star rated movies by {USER}",
    "Show the worst rated movies by {USER} and their rating",
    "What movies similar to {MOVIE} has {USER} not seen yet?",
    "What movies that star {PERSON} has {USER} seen?",
    "What movies watched by {USER} would you recommend to {USER}?",
    "What movies are in the watchlists of both {USER} and {USER}?",
    "What 10 movies would you recommend to {USER} and {USER} together?",
    "What is the shortest path between {PERSON} and {PERSON}?",
    "What is the shortest path between {MOVIE} and {MOVIE}?",
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
    }
    for placeholder, pool in replacements.items():
        if placeholder in result:
            result = result.replace(placeholder, random.choice(pool))

    return result


def get_random_examples(n: int = 6) -> list[str]:
    """Return n randomly selected and filled example questions."""
    templates = random.sample(QUESTION_TEMPLATES, n)
    return [_fill_template(t) for t in templates]
