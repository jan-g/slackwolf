import logging
from ..text import Text
from ..roles import SEER
from .base import BaseCommand, match_agent

LOG = logging.getLogger(__name__)


class SorcerorCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("At night, you may chose someone to OBSERVE in your private channel.\n"
                                "You will determine if that person is a seer."))

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("SorcerorCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != role.channel:
            return

        scry = text.match("observe", match_agent(game.players, any_agent=True))
        if scry is not None:
            target = scry[0]
            if not self.is_relevant(game=game):
                srv.broadcast(channel=channel, text=Text("You may not currently observe."))
                return True
            if target not in game.players:
                srv.broadcast(channel=channel, text=Text(target, " isn't a valid sorcery target."))
                return True
            srv.broadcast(channel=channel, text=Text("You chose to use your sorcerous sight on ", target))
            game.scratchpad.phase_actions.sorceror[role] = game.roles[target]
            return True

    def ready(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return
        game.scratchpad.phase_actions.sorceror = {}

    def resolve(self, srv=None, game=None):
        if game.current_phase.get('can_vote', False):
            return

        for role, target in game.scratchpad.phase_actions.sorceror.items():
            if target is not None:
                if target.role.name == SEER:
                    srv.broadcast(channel=role.channel,
                                  text=Text("During the night you observe ", target.player, ".\n",
                                            "They are a seer!"))
                else:
                    srv.broadcast(channel=role.channel,
                                  text=Text("During the night you observe ", target.player, ".\n",
                                            "They are not a seer."))
