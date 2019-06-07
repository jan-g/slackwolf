import logging
from ..sentinel import Sentinel
from ..text import Text, reg
from .base import BaseCommand, match_agent

LOG = logging.getLogger(__name__)
PLAYERS = Sentinel("PLAYERS")


class ProtectCommand(BaseCommand):
    matcher = reg()

    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("At night, you may chose someone to PROTECT in your private channel.\n"
                                "If that person is killed, you will die in their stead.\n"
                                "You may UNPROTECT to remove the protection."))

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("ProtectCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != role.channel:
            return

        split = text.split()
        for match, handler in self.matcher.decorated:
            result = split.match(*(m if m is not PLAYERS else match_agent(game.players, any_agent=True)
                                   for m in match))
            if result is not None:
                return handler(self, *result, srv=srv, game=game, role=role, channel=channel, text=text)

    @matcher("protect", PLAYERS)
    def protect(self, target, srv=None, game=None, role=None, channel=None, text=None):
        if not self.is_relevant(game=game):
            srv.broadcast(channel=channel, text=Text("You may not currently protect."))
            return True
        if target not in game.players:
            srv.broadcast(channel=channel, text=Text(target, " isn't a valid protection target."))
            return True
        srv.broadcast(channel=channel, text=Text("You chose to protect ", target))
        game.scratchpad.phase_actions.protect[role] = game.roles[target]
        return True

    @matcher("unprotect")
    def protect(self, srv=None, game=None, role=None, channel=None, text=None):
        if self.is_relevant(game=game):
            srv.broadcast(channel=channel, text=Text("You may not currently unprotect."))
            return True
        srv.broadcast(channel=channel, text=Text("You remove your protection."))
        game.scratchpad.phase_actions.protect[role] = None
        return True

    def ready(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return
        game.scratchpad.phase_actions.protect = {}

    def resolve(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return

        game.scratchpad.phase_actions.protected = {}

        for role, target in game.scratchpad.phase_actions.protect.items():
            if target is not None:
                srv.broadcast(channel=role.channel,
                              text=Text("During the night you protect ", target.player, "."))
                game.scratchpad.phase_actions.protected[target] = role
