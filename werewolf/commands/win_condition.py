from collections import Counter
import logging
from .base import BaseCommand
from ..roles import VILLAGERS, EVIL, WEREWOLF, HERO

LOG = logging.getLogger(__name__)


class CheckWinCondition(BaseCommand):
    def resolve(self, srv=None, game=None):
        team_counts = Counter()
        role_counts = Counter()

        for player in game.players:
            role = game.roles[player].role

            team_counts[role.team] += 1
            role_counts[role.name] += 1

        # Are all the villagers dead? Victory to team evil
        if team_counts[VILLAGERS] == 0:
            return EVIL

        # Are all the werewolves dead? Victory for the villagers
        if role_counts[WEREWOLF] == 0:
            return VILLAGERS

        # Are we down to the last two?
        if len(game.players) == 2:
            if role_counts[HERO] > 0:
                return VILLAGERS
            return EVIL

        return None
