import time
from ..game_test import simple_rules, test_game_start as game_start
from ..roles import VILLAGER, BODYGUARD, WEREWOLF, EVIL
from ..text import Text


def find_roles(*roles, game=None):
    rs = dict(game.roles)
    ans = []
    for r in roles:
        for p in game.players:
            if p in rs and rs[p].role.name == r:
                ans.append(rs[p])
                del rs[p]
                break
    return ans


def test_protect(rules=simple_rules):
    srv, bot, players, game = game_start(rules=rules)

    game.phase_shift = time.time()
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'night'

    # Locate three roles: a villager, a bodyguard, and a werewolf
    v, b, w = find_roles(VILLAGER, BODYGUARD, WEREWOLF, game=game)

    # Protect the villager!
    game.on_message(srv=srv, sender=b.player, receivers=[bot], channel=b.channel,
                    text=Text('protect', v.player))
    assert game.scratchpad.phase_actions.protect[b] == v

    # Kill the villager!
    game.on_message(srv=srv, sender=w.player, receivers=[bot], channel=game.rooms[EVIL],
                    text=Text('kill', v.player))
    assert game.scratchpad.phase_actions.kill == v

    game.phase_shift = time.time()
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'day'

    # The villager is alive
    assert v.player in game.players

    # The bodyguard is dead!
    assert b.player not in game.players

    return srv, bot, players, game
