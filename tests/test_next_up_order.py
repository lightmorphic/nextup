from datetime import date, timedelta


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


def _seed(app):
    from app import db

    # An old show never started: its next unwatched episode aired years ago.
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (801, 'Old Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (801, '2026-01-01', 0)"
    )
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, air_date) VALUES (8011, 801, 1, 1, 'Pilot', '2013-04-02')"
    )

    # A show with an episode from a few days ago.
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (802, 'New Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (802, '2026-01-01', 0)"
    )
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, air_date) VALUES (8021, 802, 3, 6, 'Latest', ?)",
        (_days_ago(3),),
    )

    # A film that reached home viewing yesterday.
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (901, 'A Film', ?)",
        (_days_ago(1),),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
        " VALUES (901, '2026-01-01', 0)"
    )

    # A film still weeks away from streaming.
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (902, 'Later Film', ?)",
        ((date.today() + timedelta(days=30)).isoformat(),),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
        " VALUES (902, '2026-01-01', 0)"
    )


def test_newest_first_puts_what_just_landed_at_the_top(app):
    from app import queries

    with app.app_context():
        _seed(app)
        items = queries.ready_to_watch("newest")
        assert [item["date"] for item in items] == sorted(
            [item["date"] for item in items], reverse=True
        )
        assert items[0]["kind"] == "film"
        assert items[0]["film"]["title"] == "A Film"
        assert items[-1]["kind"] == "episode"
        assert items[-1]["show"]["name"] == "Old Thing"


def test_oldest_first_reverses_it(app):
    from app import queries

    with app.app_context():
        _seed(app)
        items = queries.ready_to_watch("oldest")
        assert items[0]["kind"] == "episode"
        assert items[0]["show"]["name"] == "Old Thing"


def test_films_still_to_come_are_left_out(app):
    from app import queries

    with app.app_context():
        _seed(app)
        titles = [
            item["film"]["title"]
            for item in queries.ready_to_watch()
            if item["kind"] == "film"
        ]
        assert titles == ["A Film"]


def test_the_dashboard_shows_films_and_episodes_together(signed_in, app):
    with app.app_context():
        _seed(app)
    page = signed_in.get("/").get_data(as_text=True)
    assert "A Film" in page
    assert "New Thing" in page
    assert "Later Film" not in page
