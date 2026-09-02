"""Thin TMDB client.

Only the handful of endpoints Nextup needs. Every call takes the API key
from the encrypted settings store, so a missing key surfaces as a clear
error rather than a 401 from TMDB.
"""
import time

import requests

from . import secretstore

BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"
TIMEOUT = 20


class TmdbError(RuntimeError):
    pass


class MissingKey(TmdbError):
    pass


def api_key():
    key = secretstore.get("tmdb_api_key")
    if not key:
        raise MissingKey("No TMDB API key saved. Add one on the Settings page.")
    return key


def _get(path, **params):
    params["api_key"] = api_key()
    params.setdefault("language", "en-GB")
    url = f"{BASE}{path}"
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            if attempt == 2:
                raise TmdbError(f"Could not reach TMDB: {exc}") from exc
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "2")) + 1)
            continue
        if resp.status_code == 401:
            raise TmdbError("TMDB rejected the API key. Check it on the Settings page.")
        if resp.status_code == 404:
            raise TmdbError("TMDB has no record of that.")
        if not resp.ok:
            if attempt == 2:
                raise TmdbError(f"TMDB returned {resp.status_code}.")
            time.sleep(1 + attempt)
            continue
        return resp.json()
    raise TmdbError("TMDB kept rate-limiting the request.")


def search_multi(query, page=1):
    data = _get("/search/multi", query=query, page=page, include_adult="false")
    results = []
    for item in data.get("results", []):
        kind = item.get("media_type")
        if kind == "tv":
            results.append(
                {
                    "kind": "tv",
                    "id": item["id"],
                    "title": item.get("name") or "Untitled",
                    "date": item.get("first_air_date") or "",
                    "overview": item.get("overview") or "",
                    "poster_path": item.get("poster_path"),
                    "vote_average": item.get("vote_average") or 0,
                }
            )
        elif kind == "movie":
            results.append(
                {
                    "kind": "movie",
                    "id": item["id"],
                    "title": item.get("title") or "Untitled",
                    "date": item.get("release_date") or "",
                    "overview": item.get("overview") or "",
                    "poster_path": item.get("poster_path"),
                    "vote_average": item.get("vote_average") or 0,
                }
            )
    return {"results": results, "total_pages": data.get("total_pages", 1), "page": data.get("page", 1)}


def show(show_id):
    return _get(f"/tv/{show_id}")


def season(show_id, season_number):
    return _get(f"/tv/{show_id}/season/{season_number}")


def movie(movie_id):
    return _get(f"/movie/{movie_id}")


def trending_tv():
    return _get("/trending/tv/week").get("results", [])


def verify_key(candidate):
    """Check a key works before saving it."""
    try:
        resp = requests.get(
            f"{BASE}/configuration", params={"api_key": candidate}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise TmdbError(f"Could not reach TMDB: {exc}") from exc
    if resp.status_code == 401:
        raise TmdbError("TMDB rejected that key.")
    if not resp.ok:
        raise TmdbError(f"TMDB returned {resp.status_code}.")
    return True
