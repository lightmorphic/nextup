from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, queries, sync, tmdb
from ..auth import login_required
from ..redirects import back_to

bp = Blueprint("movies", __name__)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@bp.route("/movies")
@login_required
def index():
    return render_template(
        "pages/movies.html",
        to_watch=queries.movies(watched=False),
        watched=queries.movies(watched=True),
    )


@bp.route("/movie/<int:movie_id>")
@login_required
def detail(movie_id):
    row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
    if row is None:
        try:
            sync.upsert_movie(tmdb.movie(movie_id))
        except tmdb.TmdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
        if row is None:
            abort(404)
    tracked = db.query(
        "SELECT watched_at FROM tracked_movie WHERE movie_id = ?", (movie_id,), one=True
    )
    return render_template("pages/movie.html", movie=row, tracked=tracked)


@bp.route("/movie/<int:movie_id>/track", methods=["POST"])
@login_required
def track(movie_id):
    try:
        payload = tmdb.movie(movie_id)
        sync.upsert_movie(payload)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("movies.index")
    db.execute(
        "INSERT OR IGNORE INTO tracked_movie (movie_id, added_at) VALUES (?, ?)",
        (movie_id, _now()),
    )
    flash(f"Added {payload.get('title')} to your films.", "success")
    return back_to("movies.index")


@bp.route("/movie/<int:movie_id>/untrack", methods=["POST"])
@login_required
def untrack(movie_id):
    db.execute("DELETE FROM tracked_movie WHERE movie_id = ?", (movie_id,))
    return back_to("movies.index")


@bp.route("/movie/<int:movie_id>/watched", methods=["POST"])
@login_required
def watched(movie_id):
    row = db.query(
        "SELECT watched_at FROM tracked_movie WHERE movie_id = ?", (movie_id,), one=True
    )
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_movie SET watched_at = ? WHERE movie_id = ?",
        (None if row["watched_at"] else _now(), movie_id),
    )
    return back_to("movies.index")
