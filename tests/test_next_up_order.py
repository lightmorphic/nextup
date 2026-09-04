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


def _seed_behind(app):
    from app import db

    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (803, 'Behind Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (803, '2026-01-01', 0)"
    )
    for number, (title, when) in enumerate(
        [("Old One", _days_ago(60)), ("Old Two", _days_ago(40)), ("Just Aired", _days_ago(2))],
        start=1,
    ):
        db.execute(
            "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
            " name, air_date) VALUES (?, 803, 2, ?, ?, ?)",
            (8030 + number, number, title, when),
        )


def test_a_show_you_are_behind_on_is_headlined_by_the_newest_episode(app):
    from app import queries

    with app.app_context():
        _seed_behind(app)
        item = [i for i in queries.ready_to_watch() if i["kind"] == "episode"][0]
        assert item["show"]["name"] == "Behind Thing"
        assert item["episode"]["name"] == "Just Aired"
        assert item["pending"]["name"] == "Old One"
        assert item["behind"] is True
        assert item["date"] == _days_ago(2)


def test_a_caught_up_show_headlines_the_episode_you_still_need(app):
    from app import queries

    with app.app_context():
        _seed_behind(app)
        from app import db

        for episode_id in (8031, 8032):
            db.execute(
                "INSERT INTO watched_episode (episode_id, show_id, watched_at)"
                " VALUES (?, 803, '2026-01-02')",
                (episode_id,),
            )
        item = [i for i in queries.ready_to_watch() if i["kind"] == "episode"][0]
        assert item["episode"]["name"] == "Just Aired"
        assert item["pending"]["name"] == "Just Aired"
        assert item["behind"] is False


def test_the_dashboard_names_the_episode_that_just_aired(signed_in, app):
    with app.app_context():
        _seed_behind(app)
    page = signed_in.get("/").get_data(as_text=True)
    assert "Just Aired" in page
    assert "S02E03" in page
    # and still points you at the one to carry on from
    assert "Old One" in page
    assert "S02E01" in page
