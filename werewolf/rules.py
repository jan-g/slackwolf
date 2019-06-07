from functools import partial
import logging
import os.path
import yaml

from .commands import COMMANDS, DEFAULT_COMMANDS
from .phase import BasePhase
from .roles import RoleDescription, VILLAGERS, EVIL, VILLAGER, HERO, BODYGUARD, SEER, WEREWOLF, SORCEROR

LOG = logging.getLogger(__name__)

GAMES = {}


def load_game(game_def):
    game_def['roles'] = expand_roles(game_def['roles'])
    for phase in game_def.get('prelim', []) + game_def['phases']:
        phase['handler'] = BasePhase()
        resolution = [COMMANDS[resolver] for resolver in phase.get('resolution', ['vote'])]
        for i in DEFAULT_COMMANDS:
            if i not in resolution:
                resolution.append(COMMANDS[i])
        phase['resolution'] = resolution
    LOG.debug("loading game: %s", game_def)
    return game_def


def expand_roles(roles):
    rs = []
    for role in roles:
        commands = [COMMANDS[command_name] for command_name in role.get('commands', ['vote'])]
        for i in DEFAULT_COMMANDS:
            if i not in commands:
                commands.append(COMMANDS[i])
        count = role.get('count', 1)
        rooms = role.get('rooms', [])
        team = role.get('team', VILLAGERS)
        rs.extend((RoleDescription(role['name'], commands, rooms, team),) * count)
    return rs


def load_games(filename=os.path.join(os.path.dirname(__file__), 'games.yaml')):
    global GAMES
    with open(filename) as f:
        for definition in yaml.safe_load_all(f):
            if definition is None:
                continue
            GAMES[definition['name']] = partial(_predefined_game, rules=load_game(definition))
    GAMES['random'] = random_rules


def _predefined_game(rules=None, number=0):
    return rules


def game_type(name=None, number=0):
    return GAMES.get(name, lambda number=0: None)(number=number)


def random_rules(number=0):
    """Return a random setup for n players"""
    wolf = min(max(number // 3 - 1, 1), 3)
    sorc = 1 if number > 4 else 0
    seer = 1
    guard = 1 if number > 5 else 0
    hero = 1 if number > 6 else 0
    village = number - wolf - sorc - seer - guard - hero
    rules = {
        'name': 'A random game for {} players'. format(number),
        'roles': [
            {'name': VILLAGER, 'count': village},
            {'name': HERO, 'count': hero, 'commands': 'vote hero'.split()},
            {'name': BODYGUARD, 'count': guard, 'commands': 'vote protect'.split()},
            {'name': SEER, 'count': seer, 'commands': 'vote seer'.split()},
            {'name': WEREWOLF, 'count': wolf, 'team': EVIL, 'rooms': ['evil'], 'commands': 'vote kill'.split()},
            {'name': SORCEROR, 'count': sorc, 'team': EVIL, 'rooms': ['evil'], 'commands': 'vote sorceror'.split()},
        ],
        'prelim': [
            {'name': 'first night', 'handler': 'night', 'duration': '5m', 'resolution': 'sorceror seer'.split(),
             'entry_message': "An ominous night draws in.Dark clouds hide the full moon.\n"
                              "Villagers lock their doors and shutter their windows warily.",
             'exit_message': "The first night has passed uneventfully...\n"
                             "Or has it?",
             },
        ],
        'phases': [
            {'name': 'day', 'duration': '25m',
             'entry_message': "Dawn breaks over the sleepy village.\n"
                              "It is time to hunt out evil!",
             'exit_message': "Day comes to an end.\n"
                             "It is time for village justice to be served!",
             },
            {'name': 'night', 'duration': '5m', 'resolution': 'protect sorceror seer kill'.split(),
             'entry_message': "Night descends as the frightened villages scurry for shelter.\n"
                              "Evil things prowl the darkness!",
             'exit_message': "The night finally comes to an end.\n"
                             "What horrors have passed in the darkness?",
             },
        ],
    }
    return load_game(rules)
