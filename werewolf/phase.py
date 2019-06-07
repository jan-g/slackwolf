import logging
from .text import Text
from .scratchpad import ScratchPad

LOG = logging.getLogger(__name__)


class BasePhase:
    def on_entry(self, srv=None, game=None):
        """A phase is entered"""
        game.scratchpad.phase_actions = ScratchPad()  # {Type: {Role who: Role target}}
        srv.broadcast(channel=game.public, text=Text(game.current_phase['entry_message']))

        for handler in game.current_phase['resolution']:
            handler.ready(srv=srv, game=game)

    def on_exit(self, srv=None, game=None):
        """A phase finishes

        This is called to update the game state before the next phase is entered.
        It should non-null with the side name if the game has come to a conclusion."""
        srv.broadcast(channel=game.public, text=Text(game.current_phase['exit_message']))

        # Run a resolution of every phase, in order
        winner = None
        for handler in game.current_phase['resolution']:
            winner = handler.resolve(srv=srv, game=game)
            if winner is not None:
                break

        return winner

    def notice(self, game=None, running=True):
        """Return a Text item that will be appended to the pinned notice

        running is True if the phase is still on-going; otherwise False"""
        n = None
        for handler in game.current_phase['resolution']:
            n2 = handler.notice(game=game, running=running)
            if n2 is not None:
                if n is None:
                    n = n2
                else:
                    n.extend(n2)
        return n

    def action_relevant(self, game=None, command=None):
        return command in game.current_phase['resolution']
