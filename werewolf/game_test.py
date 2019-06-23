from collections import Counter
import logging
import random
import unittest
import unittest.mock
import yaml
from .service import Agent
from werewolf.service.service_test import MockService
from .game import SpecificWerewolf
from .roles import VILLAGERS, EVIL, HERO, WEREWOLF, VILLAGER, SORCEROR, SEER
from .rules import load_game, load_games, game_type
from .text import Text


load_games()


def simple_rules():
    rules = load_game(yaml.safe_load("""
name: standard
roles:
  - {name: villager, count: 3}
  - {name: hero, commands: [vote, concede, hero]}
  - {name: bodyguard, commands: [vote, concede, protect]}
  - {name: seer, commands: [vote, concede, seer]}
  - {name: werewolf, count: 2, rooms: [evil], team: evil, commands: [vote, concede, kill]}
  - {name: sorceror, team: evil, commands: [vote, concede, sorceror]}
phases:
  - name: day
    duration: 25m
    entry_message: |
      Dawn breaks over the sleepy village.
      It is time to hunt out evil!
    exit_message: |
      Day comes to an end.
      It is time for village justice to be served!
  - name: night
    duration: 5m
    resolution: [protect, sorceror, seer, kill]
    entry_message: |
      Night descends as the frightened villages scurry for shelter.
      Evil things prowl the darkness!
    exit_message: |
      The night finally comes to an end.
      What horrors have passed in the darkness?
    """))
    return rules


def standard_rules(name=None, number=0):
    def f():
        return game_type(name=name, number=number)
    return f


agent_names = 'Alice Bob Charlie Delia Emma Frank Gertrude Hector Ian Jason Kerry Liam Melanie'\
              'Natalie Owen Peter Quentin Ruth Steve Tom Uwe Wendy Xander Yvonne Zach'.split()

logging.basicConfig(level=logging.DEBUG)


def factory(rule_gen):
    rules = rule_gen()
    bot = Agent('B0', 'Bot', True, 'Robotkin')
    players = [Agent('{}'.format(agent_names[i].upper()), agent_names[i].lower(), False, agent_names[i])
               for i in range(len(rules['roles']))]

    with unittest.mock.patch('random.shuffle', new=lambda _: None):
        # Assign roles predictably
        game = SpecificWerewolf(team=None, index=0, parent=None, players=players, rules=rules)

    srv = MockService()
    return srv, bot, players, game


def test_game_start(rules=simple_rules):
    srv, bot, players, game = factory(rules)

    game.start(srv=srv, bot=bot)

    assert game.current_phase['name'] == 'day'
    assert len(srv._channel_cache) == 11    # Public, evil, 9 private channels
    assert srv._messages[game.public][-1][0] == 'DAY in the village\n'
    return srv, bot, players, game


def test_no_votes(rules=simple_rules):
    srv, bot, players, game = test_game_start(rules=rules)

    game.phase_shift = 0
    game.tick(srv=srv)

    assert len(game.players) == 9   # Still alive
    assert len(game.dead) == 0      # Nobody lynched
    assert game.current_phase['name'] == 'night'

    return srv, bot, players, game


def test_equal_votes(rules=simple_rules):
    srv, bot, players, game = test_game_start(rules=rules)

    for i in range(len(players)):
        j = (i + 1) % len(players)
        game.on_message(srv=srv, sender=players[i], channel=game.public, text=Text('vote', players[j]))

    game.phase_shift = 0
    game.tick(srv=srv)

    assert len(game.players) == 9   # Still alive
    assert len(game.dead) == 0      # Nobody lynched
    assert game.current_phase['name'] == 'night'

    return srv, bot, players, game


def test_unequal_votes(rules=simple_rules):
    srv, bot, players, game = test_game_start(rules=rules)

    for i in range(len(players)):
        j = (i + 1) % len(players)
        game.on_message(srv=srv, sender=players[i], channel=game.public, text=Text('vote', players[j]))

    game.on_message(srv=srv, sender=players[1], channel=game.public, text=Text('vote', players[0]))

    # Reset messages
    players[0]._messages = []

    game.phase_shift = 0
    game.tick(srv=srv)

    assert len(game.players) == 8         # Somebody got lynched
    assert game.dead == [players[0]]      # Player 0
    assert game.current_phase['name'] == 'night'

    return srv, bot, players, game


def test_run_to_conclusion(rules=simple_rules,
                           cast_vote=lambda game, player: True,
                           night_action=lambda game, player: (None, None)):
    srv, bot, players, game = test_game_start(rules=rules)

    while game.winner is None:
        assert game.current_phase['name'] == 'day'
        # Day phase. Everyone votes randomly
        for i in range(len(game.players)):
            j = random.randrange(len(game.players))
            if cast_vote(game, game.players[j]):
                game.on_message(srv=srv, sender=game.players[i], channel=game.public,
                                text=Text('vote', game.players[j]))

        game.phase_shift = 0
        game.tick(srv=srv)
        if game.winner is not None:
            break

        assert game.current_phase['name'] == 'night'
        # Night phase. Nobody does anything unless it's set up like that
        for p in game.players:
            channel, text = night_action(game, p)
            if channel is not None:
                game.on_message(srv=srv, channel=channel, sender=p, text=text)

        game.phase_shift = 0
        game.tick(srv=srv)

    # Tally the living and ensure we agree with the results
    teams = Counter(game.roles[p].role.team for p in game.players)
    types = Counter(game.roles[p].role.name for p in game.players)

    if teams[VILLAGERS] == 0:
        assert game.winner == EVIL
    elif teams[VILLAGERS] == teams[EVIL] == 1 and types[HERO] == 1:
        assert game.winner == VILLAGERS
    elif teams[VILLAGERS] == teams[EVIL] == 1 and types[WEREWOLF] == 1:
        assert game.winner == EVIL
    elif teams[VILLAGERS] == teams[EVIL] == 1:
        assert game.winner == VILLAGERS
    else:
        assert game.winner == VILLAGERS

    return srv, bot, players, game


def test_hero_versus_wolf(rules=simple_rules):
    def cast_vote(game, target):
        if game.roles[target].role.name == HERO:
            return False
        if [target] == [p for p in game.players if game.roles[p].role.name == WEREWOLF]:
            # Never vote for the last remaining werewolf
            return False
        return True
    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote)
    assert game.winner == VILLAGERS


def test_nonhero_versus_wolf(rules=simple_rules):
    def cast_vote(game, target):
        if [target] == [p for p in game.players if game.roles[p].role.name == VILLAGER]:
            # Never vote for the last remaining villager
            return False
        if [target] == [p for p in game.players if game.roles[p].role.name == WEREWOLF]:
            # Never vote for the last remaining werewolf
            return False
        return True
    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote)
    assert game.winner == EVIL


def test_wolf_win(rules=simple_rules):
    def cast_vote(game, target):
        # Never vote for a werewolf
        return game.roles[target].role.name != WEREWOLF
    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote)
    assert game.winner == EVIL


def test_wolf_loss(rules=simple_rules):
    def cast_vote(game, target):
        # Only vote for a werewolf
        return game.roles[target].role.name == WEREWOLF
    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote)
    assert game.winner == VILLAGERS


def test_villager_versus_sorceror(rules=simple_rules):
    def cast_vote(game, target):
        if len(game.players) > 3:
            role_name = game.roles[target].role.name
            if (role_name in (VILLAGER, SORCEROR, WEREWOLF) and
                    [target] == [ww for ww in game.players if game.roles[ww].role.name == role_name]):
                # Never vote for the last remaining villager, werewolf, or sorceror
                return False
            return True

        # Vote for the werewolf in the last three
        return game.roles[target].role.name == WEREWOLF
    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote)
    assert game.winner == VILLAGERS


def test_win_through_hunting(rules=simple_rules):
    def cast_vote(game, player):
        return False

    def night_action(game, player):
        if game.roles[player].role.name != WEREWOLF:
            return None, None

        # Pick a target player to kill
        target = random.choice([p for p in game.players if game.roles[p].role.team == VILLAGERS])
        return game.rooms[EVIL], Text('kill', target)

    srv, bot, players, game = test_run_to_conclusion(rules=rules, cast_vote=cast_vote, night_action=night_action)
    assert game.winner == EVIL


def test_loaded_game(rules=standard_rules(name="village-of-visions", number=5)):
    srv, bot, players, game = factory(rules)

    game.start(srv=srv, bot=bot)

    assert game.current_phase['name'] == 'first night'
    assert len(srv._channel_cache) == 6    # Public + 5 private channels
    assert srv._messages[game.public][-1][0] == 'FIRST NIGHT in the village\n'

    seer = game.roles[players[3]]
    assert seer.role.name == SEER
    wolf = game.roles[players[4]]
    assert wolf.role.name == WEREWOLF

    # The Seer may not act in night 0
    game.on_message(srv=srv, channel=seer.channel, sender=seer.player, text=Text("scry alice"))
    assert srv._messages[seer.channel][-1][0] == 'You may not currently scry.'

    # The Wolf may not kill in night 0
    game.on_message(srv=srv, channel=wolf.channel, sender=wolf.player, text=Text("kill alice"))
    assert srv._messages[wolf.channel][-1][0] == 'You may not currently kill.'

    # The wolf may observe during first night:
    game.on_message(srv=srv, channel=wolf.channel, sender=wolf.player, text=Text("observe delia"))
    assert srv._messages[wolf.channel][-1] == ['You chose to use your sorcerous sight on ', seer.player]

    # Day dawns
    game.phase_shift = 0
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'day'

    assert srv._messages[wolf.channel][-1] == ['During the night you observe ', seer.player, '.\n',
                                               'They are a seer!']

    # Into night with no lynch
    game.phase_shift = 0
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'night'

    # The Seer may now act
    game.on_message(srv=srv, channel=seer.channel, sender=seer.player, text=Text("scry alice"))
    assert srv._messages[seer.channel][-1] == ['You chose to scry ', players[0]]

    # The Wolf may now kill
    game.on_message(srv=srv, channel=wolf.channel, sender=wolf.player, text=Text("kill alice"))
    assert srv._messages[wolf.channel][-1] == ['The victim of the hunt is chosen: ', players[0]]

    # The wolf may continue to observe
    game.on_message(srv=srv, channel=wolf.channel, sender=wolf.player, text=Text("observe bob"))
    assert srv._messages[wolf.channel][-1] == ['You chose to use your sorcerous sight on ', players[1]]

    # Day dawns
    game.phase_shift = 0
    game.tick(srv=srv)
    assert game.current_phase['name'] == 'day'

    assert srv._messages[seer.channel][-1] == ['During the night you scry ', players[0], '.\n',
                                               'They are not a werewolf.']
    assert srv._messages[wolf.channel][-2:] == [['During the night you observe ', players[1], '.\n',
                                                 'They are not a seer.'],
                                                ['During the night you kill: ', players[0]]]

    assert game.dead == [players[0]]
    return srv, bot, players, game
