import time
from ..game_test import simple_rules, test_game_start as game_start
from ..roles import EVIL, VILLAGERS
from ..text import Text


def test_good_guys_concede(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    rs = [game.roles[p] for p in game.players if game.roles[p].role.team == VILLAGERS]
    for r in rs:
        assert game.winner is None
        game.on_message(srv=srv, sender=r.player, receivers=[bot], channel=r.channel, text=Text("concede"))

    assert game.winner == EVIL

    return srv, bot, players, game


def test_villains_concede(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    rs = [game.roles[p] for p in game.players if game.roles[p].role.team == EVIL]
    for r in rs:
        assert game.winner is None
        game.on_message(srv=srv, sender=r.player, receivers=[bot], channel=r.channel, text=Text("concede"))

    assert game.winner == VILLAGERS

    return srv, bot, players, game
