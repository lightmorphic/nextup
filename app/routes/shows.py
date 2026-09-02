from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, queries, sync, tmdb
from ..auth import login_required

bp = Blueprint("shows", __name__)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _back(default_endpoint="shows.index"):
    target = request.form.get("next") or request.referrer
    if target and target.startswith("/"):
        return redirect(target)
    return redirect(url_for(default_endpoint))


@bp.route("/shows")
@login_required
def index():
    view = request.args.get("view", "active")
    rows = queries.tracked_shows(include_archived=(view == "archived"))
    if view == "archived":
        rows = [row for row in rows if row["archived"]]
    shows = []
    for row in rows:
        shows.append(
            {
                "show": row,
                "progress": queries.show_progress(row["id"]),
                "next_up": queries.next_unwatched(row["id"]),
                "next_air": queries.next_airing(row["id"]),
            }
        )
    if view == "behind":
        shows = [item for item in shows if item["progress"]["remaining"] > 0]
    shows.sort(key=lambda item: (not item["show"]["favourite"], item["show"]["name"].lower()))
    return render_template("pages/shows.html", shows=shows, view=view)


@bp.route("/show/<int:show_id>")
@login_required
def detail(show_id):
    row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
    if row is None:
        # Not seen before - pull it straight from TMDB so the page still works.
        try:
            sync.upsert_show(tmdb.show(show_id))
        except tmdb.TmdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
        if row is None:
            abort(404)

    tracked_row = db.query(
        "SELECT archived, favourite FROM tracked_show WHERE show_id = ?", (show_id,), one=True
    )
    return render_template(
        "pages/show.html",
        show=row,
        tracked=tracked_row is not None,
        archived=bool(tracked_row and tracked_row["archived"]),
        show_favourite=bool(tracked_row and tracked_row["favourite"]),
        seasons=queries.show_seasons(show_id),
        progress=queries.show_progress(show_id),
        next_up=queries.next_unwatched(show_id),
        next_air=queries.next_airing(show_id),
    )


@bp.route("/show/<int:show_id>/track", methods=["POST"])
@login_required
def track(show_id):
    try:
        name = sync.sync_show(show_id)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return _back()
    db.execute(
        "INSERT INTO tracked_show (show_id, added_at) VALUES (?, ?)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0",
        (show_id, _now()),
    )
    flash(f"Added {name} to your shows.", "success")
    return _back("shows.index")


@bp.route("/show/<int:show_id>/untrack", methods=["POST"])
@login_required
def untrack(show_id):
    db.execute("DELETE FROM tracked_show WHERE show_id = ?", (show_id,))
    db.execute("DELETE FROM watched_episode WHERE show_id = ?", (show_id,))
    flash("Removed from your shows, along with its watched history.", "success")
    return _back("shows.index")


@bp.route("/show/<int:show_id>/archive", methods=["POST"])
@login_required
def archive(show_id):
    row = db.query("SELECT archived FROM tracked_show WHERE show_id = ?", (show_id,), one=True)
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET archived = ? WHERE show_id = ?",
        (0 if row["archived"] else 1, show_id),
    )
    return _back("shows.index")


@bp.route("/show/<int:show_id>/favourite", methods=["POST"])
@login_required
def favourite(show_id):
    row = db.query("SELECT favourite FROM tracked_show WHERE show_id = ?", (show_id,), one=True)
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET favourite = ? WHERE show_id = ?",
        (0 if row["favourite"] else 1, show_id),
    )
    return _back("shows.index")


@bp.route("/show/<int:show_id>/refresh", methods=["POST"])
@login_required
def refresh(show_id):
    try:
        sync.sync_show(show_id)
        flash("Refreshed from TMDB.", "success")
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
    return _back("shows.detail")


@bp.route("/episode/<int:episode_id>/watch", methods=["POST"])
@login_required
def watch_episode(episode_id):
    row = db.query("SELECT id, show_id FROM episode WHERE id = ?", (episode_id,), one=True)
    if row is None:
        abort(404)
    watched = db.query(
        "SELECT 1 FROM watched_episode WHERE episode_id = ?", (episode_id,), one=True
    )
    if watched:
        db.execute("DELETE FROM watched_episode WHERE episode_id = ?", (episode_id,))
    else:
        db.execute(
            "INSERT INTO watched_episode (episode_id, show_id, watched_at) VALUES (?, ?, ?)",
            (episode_id, row["show_id"], _now()),
        )
    return _back("main.dashboard")


@bp.route("/show/<int:show_id>/watch-through/<int:episode_id>", methods=["POST"])
@login_required
def watch_through(show_id, episode_id):
    """Tick this episode and everything before it - the common catch-up case."""
    target = db.query(
        "SELECT season_number, episode_number FROM episode WHERE id = ? AND show_id = ?",
        (episode_id, show_id),
        one=True,
    )
    if target is None:
        abort(404)
    rows = db.query(
        """
        SELECT e.id FROM episode e
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.show_id = ? AND w.episode_id IS NULL AND e.season_number > 0
          AND e.air_date IS NOT NULL AND e.air_date <= date('now')
          AND (e.season_number < ? OR (e.season_number = ? AND e.episode_number <= ?))
        """,
        (show_id, target["season_number"], target["season_number"], target["episode_number"]),
    )
    conn = db.get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at)"
        " VALUES (?, ?, ?)",
        [(row["id"], show_id, _now()) for row in rows],
    )
    conn.commit()
    flash(f"Marked {len(rows)} episode{'s' if len(rows) != 1 else ''} as watched.", "success")
    return _back("shows.detail")


@bp.route("/show/<int:show_id>/season/<int:season_number>/watch", methods=["POST"])
@login_required
def watch_season(show_id, season_number):
    mode = request.form.get("mode", "watch")
    if mode == "unwatch":
        db.execute(
            "DELETE FROM watched_episode WHERE episode_id IN"
            " (SELECT id FROM episode WHERE show_id = ? AND season_number = ?)",
            (show_id, season_number),
        )
    else:
        rows = db.query(
            "SELECT id FROM episode WHERE show_id = ? AND season_number = ?"
            " AND air_date IS NOT NULL AND air_date <= date('now')",
            (show_id, season_number),
        )
        conn = db.get_db()
        conn.executemany(
            "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at)"
            " VALUES (?, ?, ?)",
            [(row["id"], show_id, _now()) for row in rows],
        )
        conn.commit()
    return _back("shows.detail")
