import re
import time
import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import requests
from letterboxdpy import user, movie
from letterboxdpy.films import Films
from letterboxdpy.utils.utils_transform import get_ajax_url
from letterboxdpy.core.scraper import parse_url
from letterboxdpy.utils.utils_url import get_page_url
from letterboxdpy.utils.movies_extractor import extract_movies_from_horizontal_list, extract_movies_from_vertical_list
from soupsieve import match
from etl.src.transforms import process_cast, process_crew
import random
import time
from letterboxdpy.core.exceptions import PrivateRouteError

logger = logging.getLogger(__name__)


@dataclass
class LetterboxdUserData:
    ratings_df: pd.DataFrame
    watchlist_df: pd.DataFrame
    user_df: pd.DataFrame
    diary_df: pd.DataFrame


class LetterboxdClient:
    """
    Client to fetch user and movie data from Letterboxd.
    """

    def __init__(self, tmdb_api_key: Optional[str] = None):
        self.tmdb_api_key = tmdb_api_key

    def fetch_users_data(self, usernames: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        logger.info("Fetching Letterboxd data for %d users", len(usernames))
        data = [self._fetch_single_user(username) for username in usernames]
        return self._combine_user_data(data)

    def fetch_movie_data(self, movie_slug: str) -> Dict[str, Any]:
        logger.debug("Fetching movie '%s'...", movie_slug)

        letterboxd_props = self.get_letterboxd_props(movie_slug)
        tmdb_id = letterboxd_props['lb_tmdb_id']

        if tmdb_id and self.tmdb_api_key:
            tmdb_props = self.get_tmdb_props(tmdb_id)
        else:
            tmdb_props = {}

        return {**letterboxd_props, **tmdb_props}

    def fetch_person_data(self, tmdb_person_id: str) -> Dict[str, Any]:
        try:
            person_data = self._fetch_single_person(tmdb_person_id)
            return {
                "tmdb_id": person_data.get("id"),
                "imdb_id": person_data.get("imdb_id"),
                "name": person_data.get("name"),
                "biography": person_data.get("biography"),
                "birthday": person_data.get("birthday"),
                "deathday": person_data.get("deathday"),
                "place_of_birth": person_data.get("place_of_birth"),
                "profile_path": f"https://image.tmdb.org/t/p/original/{person_data.get('profile_path')}" if person_data.get("profile_path") else None,
                "popularity": person_data.get("popularity"),
                "gender": person_data.get("gender"),
                "known_for_department": person_data.get("known_for_department"),
                "homepage": person_data.get("homepage"),
            }

        except Exception as e:
            logger.error(f"Error fetching person data for tmdb_person_id '{tmdb_person_id}': {e}")
            return {}

    def get_letterboxd_props(self, movie_slug: str) -> Dict[str, Any]:

        movie_inst = movie.Movie(movie_slug)

        return {
            "slug": movie_slug,
            "lb_title": movie_inst.title,
            "lb_year": movie_inst.year,
            "lb_rating": movie_inst.rating if movie_inst.rating else None,
            "lb_watchers": movie_inst.get_watchers_stats().get('members'),
            "lb_runtime": movie_inst.runtime,
            "lb_plot": movie_inst.description,
            "lb_tagline": (movie_inst.tagline).upper() if movie_inst.tagline else None,
            "lb_trailer": self._extract_trailer(movie_inst),
            "lb_poster": movie_inst.poster,
            "lb_banner": movie_inst.banner,
            "lb_studios": self._extract_details(movie_inst, "studio"),
            "lb_countries": self._extract_details(movie_inst, "country"),
            "lb_languages": self._extract_details(movie_inst, "language"),
            "lb_actor_slugs": self._extract_cast(movie_inst, limit=10),
            "lb_director_slugs": self._extract_crew(movie_inst, "director"),
            "lb_genres": self._extract_themes(movie_inst, "genre"),
            "lb_themes": self._extract_themes(movie_inst, "theme"),
            "lb_mini_themes": self._extract_themes(movie_inst, "mini-theme"),
            "lb_tmdb_id": self._convert_tmdb_url_to_id(movie_inst.tmdb_link) if movie_inst.tmdb_link else None,
            "lb_imdb_id": self._convert_imdb_url_to_id(movie_inst.imdb_link) if movie_inst.imdb_link else None,
            "lb_letterboxd_id": movie_inst.id,
            "lb_tmdb_url": movie_inst.tmdb_link,
            "lb_imdb_url": movie_inst.imdb_link,
            "lb_letterboxd_url": movie_inst.url,
        }

    def get_tmdb_props(self, tmdb_id: str) -> Dict[str, Any]:

        try:
            details = self._fetch_tmdb_details(tmdb_id)
            cast, crew = self._fetch_tmdb_credits(tmdb_id)
            key_words = self._fetch_tmdb_keywords(tmdb_id)

            return {

                "belongs_to_collection": details.get("belongs_to_collection"),
                "budget": details.get("budget"),
                "status": details.get("status"),
                "homepage": details.get("homepage"),
                "overview": details.get("overview"),
                "original_language": details.get("original_language"),
                "original_title": details.get("original_title"),
                "popularity": details.get("popularity"),
                "release_date": details.get("release_date"),
                "revenue": details.get("revenue"),
                "cast": cast,
                "crew": crew,
                "keywords": key_words,
                "runtime": details.get("runtime"),
                "tmdb_id": details.get("id"),
                "imdb_id": details.get("imdb_id"),
                "tagline": details.get("tagline"),
                "title": details.get("title"),
                "vote_count": details.get("vote_count"),
                "vote_average": details.get("vote_average"),
                "backdrop_path": f"https://image.tmdb.org/t/p/original/{details.get('backdrop_path')}" if details.get("backdrop_path") else None,
                "poster_path": f"https://image.tmdb.org/t/p/original/{details.get('poster_path')}" if details.get("poster_path") else None,
                "genres": details.get("genres"),
                "production_companies": details.get("production_companies"),
                "production_countries": details.get("production_countries"),
                "spoken_languages": details.get("spoken_languages"),
            }
        except Exception as e:
            logger.error(f"Error fetching TMDb data for tmdb_id '{tmdb_id}': {e}")
            return {}

    def get_trending_movies(self, from_csv: bool = False) -> pd.DataFrame:
        """
        Fetch trending movies of this week from Letterboxd.
        """
        logger.info("Fetching trending movies from Letterboxd")
        films_instance = Films("https://letterboxd.com/films/popular/this/week/", max=25)
        slugs = [film.slug for film in films_instance.movies]
        return pd.DataFrame({"slug": slugs, "rank": range(1, len(slugs) + 1)})

    # -----------------------------------------------------------------
    # User helpers
    # -----------------------------------------------------------------

    # def _fetch_single_user(self, username: str) -> LetterboxdUserData:
    #     logger.info("Fetching data for '%s'", username)
    #     time.sleep(0.2)
    #     user_inst = user.User(username)

    #     return LetterboxdUserData(
    #         ratings_df=self._ratings_df(username, user_inst),
    #         watchlist_df=self._watchlist_df(username, user_inst),
    #         user_df=self._profile_df(username, user_inst),
    #     )

    def _fetch_single_user(self, username: str) -> LetterboxdUserData:  # type: ignore
        logger.info("Fetching data for '%s'", username)

        for attempt in range(3):
            try:
                if attempt > 0:
                    sleep = 2 ** attempt + random.uniform(0.5, 1.5)
                    logger.warning(
                        "Retry %s for %s after %.2fs", attempt, username, sleep
                    )
                    time.sleep(sleep)

                user_inst = user.User(username)

                return LetterboxdUserData(
                    ratings_df=self._ratings_df(username, user_inst),
                    watchlist_df=self._watchlist_df(username, user_inst),
                    user_df=self._profile_df(username, user_inst),
                    diary_df=self._diary_df(username, user_inst),
                )

            except PrivateRouteError as e:
                if attempt == 2:
                    raise

    def _combine_user_data(
        self, data: List[LetterboxdUserData]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:

        return (
            pd.concat([d.ratings_df for d in data], ignore_index=True),
            pd.concat([d.watchlist_df for d in data], ignore_index=True),
            pd.concat([d.user_df for d in data], ignore_index=True),
            pd.concat([d.diary_df for d in data], ignore_index=True),
        )

    def _ratings_df(self, username: str, user_inst: user.User) -> pd.DataFrame:
        print(f"Fetching ratings for {username}...")

        films = user_inst.get_films()["movies"]
        # print(films)

        df = pd.DataFrame(
            {
                "username": username,
                "slug": slug,
                "rating": info.get("rating"),
                "liked": info.get("liked"),
            }
            for slug, info in films.items()
        )
        return df[df["rating"].notna()]

    def _watchlist_df(self, username: str, user_inst: user.User) -> pd.DataFrame:
        watchlist = user_inst.get_watchlist().get("data", {})
        return pd.DataFrame(
            {"username": username, "slug": item.get("slug")}
            for item in watchlist.values()
        )

    def _profile_df(self, username: str, user_inst: user.User) -> pd.DataFrame:
        return pd.DataFrame(
            [{
                "username": username,
                "display_name": user_inst.display_name,
                "avatar": user_inst.avatar.get("url"),  # type: ignore
                "url": user_inst.url,
            }]
        )

    def _diary_df(self, username: str, user_inst: user.User) -> pd.DataFrame:
        entries = user_inst.get_diary().get("entries", {})
        return pd.DataFrame(
            {
                "username": username,
                "entry_id": entry_id,
                "slug": info.get("slug"),
                "name": info.get("name"),
                "rewatched": info.get("actions", {}).get("rewatched"),
                "rating": info.get("actions", {}).get("rating"),
                "liked": info.get("actions", {}).get("liked"),
                "reviewed": info.get("actions", {}).get("reviewed"),
                "date": info.get("date"),
                "page_url": (info.get("page") or {}).get("url"),
                "page_no": (info.get("page") or {}).get("no"),
            }
            for entry_id, info in entries.items()
        )

    # -----------------------------------------------------------------
    # Movie helpers
    # -----------------------------------------------------------------

    def _extract_trailer(self, movie_inst: movie.Movie) -> str:
        return movie_inst.trailer["link"] if movie_inst.trailer else ""

    def _extract_details(self, movie_inst: movie.Movie, kind: str) -> List[str]:
        return [d["name"] for d in movie_inst.details if d["type"] == kind]

    def _extract_cast(self, movie_inst: movie.Movie, limit: Optional[int] = None) -> List[str]:
        cast = movie_inst.cast
        if limit:
            cast = cast[:limit]
        return [actor["slug"] for actor in cast]

    def _extract_crew(self, movie_inst: movie.Movie, kind: str) -> Optional[List[str]]:
        directors = movie_inst.crew.get(kind, [])
        return [d["slug"] for d in directors] if directors else None

    def _extract_themes(self, movie_inst: movie.Movie, kind: str):
        return [{"name": g["name"]} for g in movie_inst.genres if g["type"] == kind]

    def _convert_imdb_url_to_id(self, imdb_url: str) -> Optional[str]:
        match = re.search(r"(tt\d+)", imdb_url)
        return match.group(1) if match else None

    def _convert_tmdb_url_to_id(self, tmdb_url: str) -> Optional[str]:
        match = re.search(r"/(movie|tv)/(\d+)", tmdb_url)
        return match.group(2) if match else None

    # -----------------------------------------------------------------
    # TMDb helpers, serves as fallback for missing data
    # -----------------------------------------------------------------

    def _fetch_tmdb_credits(self, tmdb_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={self.tmdb_api_key}"
        time.sleep(0.2)  # basic rate limiting
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        return process_cast(data.get("cast", [])), process_crew(data.get("crew", []))

    def _fetch_tmdb_details(self, tmdb_id: str) -> Dict[str, Any]:
        time.sleep(0.2)
        url = "https://api.themoviedb.org/3/movie/{}?api_key={}".format(tmdb_id, self.tmdb_api_key)
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data

    def _fetch_tmdb_keywords(self, tmdb_id: str) -> List[Dict[str, Any]]:
        time.sleep(0.2)
        url = "https://api.themoviedb.org/3/movie/{}/keywords?api_key={}".format(tmdb_id, self.tmdb_api_key)
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("keywords", [])

    def _fetch_single_person(self, person_id: str) -> Dict[str, Any]:
        time.sleep(0.2)
        url = "https://api.themoviedb.org/3/person/{}?api_key={}".format(person_id, self.tmdb_api_key)
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data


if __name__ == "__main__":

    # user_data = client._fetch_single_user("sverlaan")
    user_instance = user.User("sverlaan")

    # show response of the first entry
    # print(list(user_instance.get_diary()["entries"].values())[5])
    # print(user_instance.get_reviews())

    # movie_inst = movie.Movie("inception")
    # print(movie_inst.get_watchers_stats()['members'])

    # client = LetterboxdClient(tmdb_api_key="")
    # # movie_data = client.fetch_movie_data("groener-gras")
    # data = client.fetch_person_data("1234")

    # client = LetterboxdClient(tmdb_api_key="")
    # trending_df = client.get_trending_movies()
    # print(trending_df)
