from collections import namedtuple
import logging
from .text import Text

LOG = logging.getLogger(__name__)


RoleDescription = namedtuple('RoleDescription', ('name', 'commands', 'rooms', 'team'))
VILLAGERS = 'villagers'
EVIL = 'evil'
VILLAGER = 'villager'
HERO = 'hero'
BODYGUARD = 'bodyguard'
SEER = 'seer'
WEREWOLF = 'werewolf'
SORCEROR = 'sorceror'


class BaseRole:
    is_good = True

    @property
    def is_evil(self):
        return not self.is_good

    def __init__(self, player, role):
        self.player = player
        self.channel = None     # Private channel
        self.channels = {}      # Any other group channels: str(name) -> Channel
        self.role = role

    def welcome(self, srv=None, channel=None, game=None):
        self.channel = channel
        srv.broadcast(channel=channel, text=Text("Your role: ", self.role.name))
        for command in self.role.commands:
            command.welcome(srv=srv, game=game, role=self)

    def on_message(self, srv=None, game=None, channel=None, text=None):
        for command in self.role.commands:
            if command.on_message(srv=srv, game=game, role=self, channel=channel, text=text):
                return True
        return False

    def __repr__(self):
        return 'BaseRole(player={!r}, role={!r})'.format(self.player, self.role)
