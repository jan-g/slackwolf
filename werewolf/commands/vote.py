from collections import defaultdict
import logging
from ..text import Text
from .base import BaseCommand, match_agent

LOG = logging.getLogger(__name__)


class VoteCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("During the day, you may VOTE in the public channel.\n"
                                "During the day, you may REMOVE VOTE in the public channel."))

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("VoteCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != game.public:
            return

        vote = text.match("vote", match_agent(game.players, any_agent=True))
        if vote is not None:
            target = vote[0]
            if not self.is_relevant(game=game):
                srv.broadcast(channel=channel, text=Text("You may not currently vote."))
                return True
            if target not in game.players:
                srv.broadcast(channel=channel, text=Text(target, " isn't a valid vote target."))
                return True
            srv.broadcast(channel=channel, text=Text("A vote is cast!"))
            game.scratchpad.vote_history.append((role, game.roles[target]))
            return True

        vote = text.match("remove", "vote")
        if vote is not None:
            if not self.is_relevant(game=game):
                srv.broadcast(channel=channel, text=Text("You may not currently vote."))
                return True
            srv.broadcast(channel=channel, text=Text("A vote is removed."))
            game.scratchpad.vote_history.append((role, None))
            return True

    def ready(self, srv=None, game=None):
        # Clear any and all votes
        game.scratchpad.vote_history = []

    def resolve(self, srv=None, game=None):
        text, first, draw = _count_votes(game=game)
        text = Text("The votes are tallied:\n") + text
        if first is not None:
            text.extend((first.player, " was lynched. They were a ", first.role.name, "."))
            game.dead.append(first.player)
            game.players.remove(first.player)
        elif draw:
            text.append("Nobody was executed due to a tie.")
        else:
            text.append("Nobody was executed.")
        srv.broadcast(channel=game.public, text=text)

    def notice(self, game=None, running=True):
        if running:
            text, first, draw = _count_votes(game=game)
            text = Text("Votes stand as follows:\n") + text
            if first is not None:
                text.extend((first.player, " is currently in line to be lynched."))
            elif draw:
                text.append("Nobody will be executed in the case of a tie.")
            else:
                text.append("Nobody will be executed.")
            return text

        else:
            text, first, draw = _count_votes(game=game)
            text = Text("Votes were as follows:\n") + text
            if first is not None:
                text.extend((first.player, " was lynched."))
            elif draw:
                text.append("Nobody was executed due to a tie.")
            else:
                text.append("Nobody was executed.")
            return text


def _count_votes(game=None):
    # Summarise the votes thus far
    votes = defaultdict(list)  # target Role: [voting Role]
    voters = {}  # voting Role: target Role
    for voter, target in game.scratchpad.vote_history:
        if voter in voters:
            old_target = voters[voter]
            if old_target in votes:
                votes[old_target].remove(voter)
        voters[voter] = target
        if target is not None:
            votes[target].append(voter)

    text = Text()
    LOG.debug("votes: %s voters: %s", votes, voters)
    first = None
    max_len = 0
    draw = False
    for target in sorted(votes, key=lambda role: role.player.name):
        voters = votes[target]
        if len(voters) == 0:
            continue
        text.extend((target.player, ": ", len(voters), " "))
        text.extend(voter.player for voter in voters)
        text.append("\n")
        if len(voters) == max_len and max_len > 0:
            first = None
            draw = True
        elif len(voters) > max_len:
            max_len = len(voters)
            first = target
            draw = False

    return text, first, draw
