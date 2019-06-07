import logging
from ..service import Agent

LOG = logging.getLogger(__name__)


def match_agent(agents=None, any_agent=False):
    def match(item):
        if isinstance(item, Agent) and (any_agent or item in agents):
            return item
        elif isinstance(item, str):
            matches = {agent
                       for agent in agents
                       if agent.name.lower().startswith(item.lower())
                       or agent.real_name.lower().startswith(item.lower())}
            LOG.debug("matching agents for %s amongst %r", item, agents)
            if len(matches) == 1:
                return matches.pop()
    return match


class BaseCommand:
    def welcome(self, srv=None, game=None, role=None):
        """Send an introductory message, if appropriate"""
        pass

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        """When a message is received by a player in a particular channel, handle it

        Text turns up as already split ready for matching."""
        pass

    def ready(self, srv=None, game=None):
        """As a phase starts, these steps are called in order

        They should ready the scratchpad if required."""

    def resolve(self, srv=None, game=None):
        """As a phase exits, these resolution phases are called in order

        They should update the scratchpad if required.
        Then they should make any reports required.

        Return None if there is no winner; otherwise, return the winner's side.
        The first resolution mechanism to declare a winner will be the value taken."""
        return None

    def is_relevant(self, game=None):
        return game.current_phase['handler'].action_relevant(game=game, command=self)

    def notice(self, game=None, running=True):
        """Return any text to add to the day's notice

        `running` will be True if this phase is still going,
        or False if the phase is concluded.

        Return None - or Text to be appended to the game notice."""
        return None
