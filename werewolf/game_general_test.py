from .game import GeneralWerewolf
from .game_test import agent_names
from .service import Agent
from werewolf.service.service_test import MockService
from .text import Text


def factory():
    srv = MockService()
    bot = Agent('B0', 'Bot', True, 'Robotkin')
    channel = srv.new_channel(name="general", private=False, invite=[bot])
    players = [Agent('{}'.format(n.upper()), n.lower(), False, n) for n in agent_names]

    game = GeneralWerewolf()
    return srv, channel, bot, players, game


def test_start_verb():
    srv, channel, bot, players, game = factory()

    game.on_message(srv=srv, sender=players[0], receivers=[bot], channel=channel,
                    text=Text(bot, 'start village-of-visions', players[0], players[1], players[2]))

    assert srv._messages[channel][-1] == ['A ', 'village-of-visions', ' game requires ', 5, ' players']
