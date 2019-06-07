from datetime import datetime, timezone
import unittest.mock
import time
from ..game_test import simple_rules, test_game_start as game_start
from ..text import Text


def test_advancing(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    for p in players:
        assert game.current_phase['name'] == 'day'
        game.on_message(srv=srv,  sender=p, receivers=[bot], channel=game.public, text=Text("advance"))

    assert game.current_phase['name'] == 'night'

    return srv, bot, players, game


def test_schedule_duration_only(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    p = players[0]

    start = game.phase_start

    game.on_message(srv=srv, sender=p, receivers=[bot], channel=game.public,
                    text=Text("schedule day 1m40s"))
    assert 99 <= game.phase_shift - start <= 101

    # Advance through night into the next day
    game.phase_shift = time.time()
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'night'

    game.phase_shift = time.time()
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'day'

    assert 99 <= game.phase_shift - game.phase_start <= 101


def test_schedule_update(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    fake_now = datetime(2019, 6, 21, 15, 40, tzinfo=timezone.utc).timestamp()
    with unittest.mock.patch('time.time', new=lambda: fake_now):
        p = players[0]

        game.on_message(srv=srv, sender=p, receivers=[bot], channel=game.public,
                        text=Text("schedule day 0s mon-wed 10-12:01"))

        assert game.phase_shift == datetime(2019, 6, 24, 10, tzinfo=timezone.utc).timestamp()

    with unittest.mock.patch('time.time', new=lambda: fake_now):
        p = players[0]

        game.on_message(srv=srv, sender=p, receivers=[bot], channel=game.public,
                        text=Text("schedule day 30s mon-wed 10-12:01"))

        assert game.phase_shift == datetime(2019, 6, 24, 10, 0, 30, tzinfo=timezone.utc).timestamp()


def test_schedule_complex(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    fake_now = datetime(2019, 6, 21, 15, 40, tzinfo=timezone.utc).timestamp()
    with unittest.mock.patch('time.time', new=lambda: fake_now):
        p = players[0]

        game.on_message(srv=srv, sender=p, receivers=[bot], channel=game.public,
                        text=Text("schedule day 0s mon-wed 12-12:01"))

        game.on_message(srv=srv, sender=p, receivers=[bot], channel=game.public,
                        text=Text("schedule night 0s mon-wed 15-15:01"))

        assert game.current_phase['name'] == 'day'
        assert game.phase_shift == datetime(2019, 6, 24, 12, tzinfo=timezone.utc).timestamp()

    fake_now = game.phase_shift
    with unittest.mock.patch('time.time', new=lambda: fake_now):
        game.tick(srv=srv)
        assert game.current_phase['name'] == 'night'

        assert game.phase_shift == datetime(2019, 6, 24, 15, tzinfo=timezone.utc).timestamp()

    fake_now = game.phase_shift
    with unittest.mock.patch('time.time', new=lambda: fake_now):
        game.tick(srv=srv)
        assert game.current_phase['name'] == 'day'

        assert game.phase_shift == datetime(2019, 6, 25, 12, tzinfo=timezone.utc).timestamp()
