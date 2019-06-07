from .schedule import ScheduleCommand
from .concede import ConcedeCommand
from .win_condition import CheckWinCondition
from .vote import VoteCommand
from .kill import KillCommand
from .protect import ProtectCommand
from .seer import SeerCommand
from .sorceror import SorcerorCommand
from .hero import HeroCommand

COMMANDS = {
    'schedule': ScheduleCommand(),
    'concede': ConcedeCommand(),

    'vote': VoteCommand(),
    'kill': KillCommand(),
    'protect': ProtectCommand(),
    'seer': SeerCommand(),
    'sorceror': SorcerorCommand(),
    'hero': HeroCommand(),

    'check_win': CheckWinCondition(),
}

DEFAULT_COMMANDS = 'schedule concede check_win'.split()
