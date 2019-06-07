import logging
from ..text import Text
from ..roles import EVIL
from .base import BaseCommand, match_agent

LOG = logging.getLogger(__name__)


class KillCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        if EVIL in game.rooms:
            srv.broadcast(channel=role.channel,
                          text=Text("At night, you may chose a victim to KILL in the evil channel.\n"
                                    "Only one victim will be selected."))
        else:
            game.rooms[EVIL] = role.channel
            srv.broadcast(channel=role.channel,
                          text=Text("At night, you may chose a victim to KILL in your private channel.\n"
                                    "Only one victim will be selected."))

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("KillCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != game.rooms[EVIL]:
            return

        kill = text.match("kill", match_agent(game.players, any_agent=True))
        if kill is not None:
            target = kill[0]
            if not self.is_relevant(game=game):
                srv.broadcast(channel=channel, text=Text("You may not currently kill."))
                return True
            if target not in game.players:
                srv.broadcast(channel=channel, text=Text(target, " isn't a valid kill target."))
                return True
            srv.broadcast(channel=channel, text=Text("The victim of the hunt is chosen: ", target))
            game.scratchpad.phase_actions.kill = game.roles[target]
            return True

    def ready(self, srv=None, game=None):
        game.scratchpad.killed = None
        if not self.is_relevant(game=game):
            return
        game.scratchpad.phase_actions.kill = None

    def resolve(self, srv=None, game=None):
        if not self.is_relevant(game=game):
            return

        game.scratchpad.killed = None

        # Is this player killed?
        target = game.scratchpad.phase_actions.kill
        if target is None:
            srv.broadcast(channel=game.rooms[EVIL],
                          text=Text("You do not attempt to kill anyone during the night."))
            return

        killed = game.scratchpad.killed = game.scratchpad.phase_actions.protected.get(target, target)

        if killed == target:
            srv.broadcast(channel=game.rooms[EVIL],
                          text=Text("During the night you kill: ", target.player))
        else:
            srv.broadcast(channel=game.rooms[EVIL],
                          text=Text("During the night you try to kill ", target.player,
                                    " but ", killed.player, " dies instead."))

        srv.broadcast(channel=killed.channel,
                      text=Text("During the night you fall to werewolves.\n"
                                "Refrain from speaking in the public channel until the game is concluded."))
        srv.broadcast(channel=game.public,
                      text=Text(killed.player, " was murdered in the night. They were a ", killed.role.name, "!"))

        game.dead.append(killed.player)
        game.players.remove(killed.player)

    def notice(self, game=None, running=True):
        LOG.debug("NightPhase notice - scratchpad is %s", game.scratchpad)
        if running:
            return

        if game.scratchpad.killed is not None:
            # It'll contain a Role
            return Text("Someone died in the night: ", game.scratchpad.killed.player)
        else:
            return Text("Nobody died in the night.")
