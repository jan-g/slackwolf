from collections import Counter
import logging
from ..text import Text
from .base import BaseCommand

LOG = logging.getLogger(__name__)


class ConcedeCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("At any point, you may CONCEDE in your private channel.\n"
                                "If all players on your team do so, you will automatically forfeit the game."))

    def ready(self, srv=None, game=None):
        game.scratchpad.concessions = set()

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("ConcedeCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != role.channel:
            return False

        cmd = text.match("concede")
        if cmd is not None:
            srv.broadcast(channel=role.channel, text=Text("Your concession is noted."))
            game.scratchpad.concessions.add(role)

            winner = _check_concession(game=game)
            if winner is not None:
                game.winner = winner
                srv.post_notice(channel=game.public,
                                text=Text("Through concessions, a side emerges victorious: ", winner))

            return True


def _check_concession(game=None):
    if len(game.scratchpad.concessions) == 0:
        return None

    concessions = Counter()
    team_counts = Counter()

    for player in game.players:
        role = game.roles[player].role
        team_counts[role.team] += 1

    for player in game.scratchpad.concessions:
        concessions[player.role.team] += 1

    # Have all members of all but one side conceded?
    teams = set(team_counts)
    for team in team_counts:
        if concessions[team] == team_counts[team]:
            teams.discard(team)

    if len(teams) == 1:
        return teams.pop()

    return None
