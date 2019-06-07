import logging
import time
from ..schedule import parse as time_parse, Schedule
from ..text import Text, reg
from .base import BaseCommand

LOG = logging.getLogger(__name__)


class ScheduleCommand(BaseCommand):
    matcher = reg()

    def welcome(self, srv=None, game=None, role=None):
        srv.broadcast(channel=role.channel,
                      text=Text("You may alter the schedule for play.\n"
                                "You can ADVANCE in the main room. If unanimous, the current phase will end.\n"
                                "You can SCHEDULE {phase name} {new duration} {new schedule}"
                                " to adjust the automatic schedule.\n"
                                "If you do this, the end of the current phase will be altered."))

    def ready(self, srv=None, game=None):
        game.scratchpad.advances = set()

    def on_message(self, srv=None, game=None, role=None, channel=None, text=None):
        LOG.debug("AdvanceCommand examines: game=%s, role=%s, channel=%s, text=%s", game, role, channel, text)
        if channel != game.public:
            return False

        split = text.split()
        for match, handler in self.matcher.decorated:
            result = split.match(*match)
            if result is not None:
                return handler(self, *result, srv=srv, game=game, role=role, channel=channel, text=text)

    @matcher("advance")
    def advance(self, srv=None, game=None, role=None, channel=None, text=None):
        game.scratchpad.advances.add(role)
        if len(game.scratchpad.advances) == len(game.players):
            srv.broadcast(channel=game.public,
                          text=Text("By unanimous agreement of the remaining players, this phase advances."))
            game.phase_shift = time.time()
            return True

    @matcher("schedule", str, str, [str])
    def schedule(self, phase_name, duration, schedule, srv=None, game=None, role=None, channel=None, text=None):
        for phase in game.rules.get('prelim', []) + game.rules['phases']:
            if phase_name == phase['name']:
                break
        else:
            return

        phase['duration'] = duration
        duration = time_parse(duration)

        if len(schedule) > 0:
            phase['schedule'] = Schedule(' '.join(schedule))

        if game.current_phase is phase:
            game.phase_shift = phase['schedule'].next_time_in_period(delta=duration)

        srv.whisper(channel=game.public, agent=role.player, text=Text("Schedule updated."))
        return True
