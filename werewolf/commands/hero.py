import logging
from ..text import Text
from .base import BaseCommand

LOG = logging.getLogger(__name__)


class HeroCommand(BaseCommand):
    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("You are heroic. This has no special actions.\n"
                                "Your team will win should you end up in the final two with a werewolf."))
