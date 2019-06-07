import logging
from ..text import Text
from ..roles import WEREWOLF
from .base import BaseCommand, match_agent

LOG = logging.getLogger(__name__)


class SeerCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("At night, you may chose someone to SCRY in your private channel.\n"
                                "You will determine if that person is a werewolf.\n"
                                "Evil humans are not detected."))

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("SeerCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != role.channel:
            return

        scry = text.match("scry", match_agent(game.players, any_agent=True))
        if scry is not None:
            target = scry[0]
            if not self.is_relevant(game=game):
                srv.broadcast(channel=channel, text=Text("You may not currently scry."))
                return True
            if target not in game.players:
                srv.broadcast(channel=channel, text=Text(target, " isn't a valid scrying target."))
                return True
            srv.broadcast(channel=channel, text=Text("You chose to scry ", target))
            game.scratchpad.phase_actions.scry[role] = game.roles[target]
            return True

    def ready(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return
        game.scratchpad.phase_actions.scry = {}

    def resolve(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return

        for role, target in game.scratchpad.phase_actions.scry.items():
            if target is not None:
                if target.role.name == WEREWOLF:
                    srv.broadcast(channel=role.channel,
                                  text=Text("During the night you scry ", target.player, ".\n",
                                            "They are a werewolf!"))
                else:
                    srv.broadcast(channel=role.channel,
                                  text=Text("During the night you scry ", target.player, ".\n",
                                            "They are not a werewolf."))
