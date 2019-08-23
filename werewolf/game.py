from collections import defaultdict
import logging
import random
import time
from uuid import uuid4 as uuid

from .dispatch import BaseDispatch, NewTarget, DeleteTarget
from .schedule import parse as time_parse
from .persist import save, drop
from .roles import BaseRole
from .rules import game_type
from .schedule import EmptySchedule
from .scratchpad import ScratchPad
from .service import Agent
from .text import Text, reg

LOG = logging.getLogger(__name__)


class GeneralWerewolf(BaseDispatch):
    matcher = reg()

    def __init__(self, index=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if index is None:
            index = 0
        self.index = index
        self.oauth_state = None

    def on_message(self, srv=None, sender=None, receivers=None, channel=None, text=None):
        me = receivers[0]

        LOG.debug("%s -> %s on %s: %r", sender, receivers, channel, text)
        split = text.split()
        for match, handler in self.matcher.decorated:
            result = split.match(*(me if m is self.matcher.me else m for m in match))
            if result is not None:
                return handler(self, *result, srv=srv, sender=sender, channel=channel, bot=me, text=text)

    @matcher(matcher.me, "start", str, [Agent])
    def start(self, game_name, players, srv=None, channel=None, bot=None, sender=None, text=None):
        players = list(set(players))
        rules = game_type(name=game_name, number=len(players))
        if rules is None:
            srv.broadcast(channel, Text("I don't know how to play a game of ", game_name))
            return
        LOG.debug("rules are %s", rules)
        if len(players) != len(rules['roles']):
            srv.broadcast(channel, Text("A ", game_name, " game requires ", len(rules['roles']), " players"))
            return

        # Make a channel for those users
        LOG.info("New game starting for %s", players)
        self.index += 1
        game = SpecificWerewolf(team=srv.team, index=self.index, parent=channel, players=players, rules=rules)
        self.persist()
        return game.start(srv=srv, bot=bot)

    @matcher(matcher.me, "delete", str)
    def delete(self, channel_name, srv=None, channel=None, bot=None, sender=None, text=None):
        def locate_channel(driver, name):
            LOG.debug("hunting for %s in %s", name, driver.channel_map)
            for c in driver.channel_map:
                LOG.debug("testing %s", c)
                if c.name == name:
                    return c

        def find_and_delete_channel(driver):
            channel = locate_channel(driver, channel_name)
            if channel is not None:
                LOG.warning("deleting channel %s", channel)
                srv.delete_channel(channel=channel)

        return find_and_delete_channel,

    @matcher(matcher.me, "oauth", [str])
    def do_oauth(self, scopes, srv=None, channel=None, bot=None, sender=None, text=None):
        scope = ' '.join(scopes)
        state = str(uuid())
        self.oauth_state = (state, scope)
        uri = srv.oauth_uri(state=state, scope=scope)
        srv.broadcast(channel=channel, text=Text(uri))

    @matcher(matcher.me, "advance", str)
    def do_advance(self, channel_name, srv=None, channel=None, bot=None, sender=None, text=None):
        def locate_target(driver, name):
            LOG.debug("hunting for %s in %s", name, driver.channel_map)
            for c in driver.channel_map:
                LOG.debug("testing %s", c)
                if c.name == name:
                    return driver.channel_map[c]

        def find_and_advance_game(driver):
            game = locate_target(driver, channel_name)
            if game is not None:
                game.phase_shift = time.time()
                game.tick(srv=srv)

        return find_and_advance_game,

    def oauth_callback(self, srv=None, code=None, state=None):
        if state != self.oauth_state[0]:
            LOG.warning("Unmatching oauth state token: state=%s != %s, code=%s", state, self.oauth_state, code)
            return
        response = srv.oauth_complete(code=code)
        LOG.info("oauth response: %s", response)

    def persist(self):
        save('default', self)

    def save(self):
        return self.index

    @classmethod
    def load(cls, value):
        return cls(index=value)


class SpecificWerewolf(BaseDispatch):
    def __init__(self, team=None, index=None, parent=None, players=None, rules=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.team = team
        self.base_name = '{}-{}'.format('ww', index)
        self.players = sorted(players, key=lambda player: (player.name, player.id))
        self.dead = []
        self.public = None
        self.rules = rules
        self.prelim = 0     # Walk once through preliminary phases
        self.phase = 0      # Cycle through main phases
        self.winner = None

        # Allocate roles to players
        random.shuffle(players)
        self.roles = {}     # Player: BaseRole
        self.room_map = defaultdict(list)   # room_name: [Player]
        self.rooms = {}     # room_name: Channel
        self.channels = defaultdict(list)   # Channel: [BaseRole]
        for player, role in zip(players, rules['roles']):
            self.roles[player] = BaseRole(player, role)
            for room in role.rooms:
                self.room_map[room].append(player)

        self.notice = None      # The public description of state of play in this phase
        self.phase_start = self.phase_shift = None  # When the phase starts/ends
        self.scratchpad = ScratchPad()
        for phase in self.rules.get('prelim', []) + self.rules['phases']:
            phase['schedule'] = EmptySchedule()

    def start(self, srv=None, bot=None):
        self.public = srv.new_channel(name=self.base_name, invite=[bot] + self.players)
        text = Text("A new game begins with ") + self.players + Text("\n")
        blurb = self.rules.get('blurb')
        if blurb is not None:
            text.append(blurb)
        srv.broadcast(self.public, text)

        for room, players in self.room_map.items():
            channel = srv.new_channel(name='{}-{}'.format(self.base_name, room),
                                      private=True,
                                      invite=[bot] + players)
            self.rooms[room] = channel
            self.channels[channel] = [self.roles[player] for player in players]

        personal_channels = []
        for player, role in self.roles.items():
            channel = srv.new_channel(name='{}-{}'.format(self.base_name, player.name),
                                      private=True,
                                      invite=[bot, player])
            role.welcome(srv=srv, channel=channel, game=self)
            personal_channels.append(role.channel)
            self.channels[channel] = [self.roles[player]]

        self.enter_phase(srv=srv)
        return NewTarget(self, [self.public] + list(self.rooms.values()) + personal_channels),

    def on_message(self, srv=None, sender=None, receivers=None, channel=None, text=None):
        if self.winner is not None:
            return

        if sender not in self.roles:
            LOG.warning("unknown message arriving on %s, from %s: %r", channel, sender, text)
            return

        if sender not in self.players:
            if channel == self.public:
                srv.delete_message(channel=channel, message_id=text.message_id)
                srv.whisper(channel=channel, agent=sender, text=Text("You're dead, shush."))
            else:
                srv.broadcast(channel=channel, text=Text("You're dead, shush."))
            return

        LOG.info("dispatching message on %s from %s: %s to %s", channel, sender, text, self.roles[sender])
        if self.roles[sender].on_message(srv=srv, game=self, channel=channel, text=text.split()):
            # If something happened, let's potentially advance the game state in response
            return self.tick(srv=srv)
        return

    @property
    def current_phase(self):
        if self.prelim < len(self.rules.get('prelim', [])):
            return self.rules['prelim'][self.prelim]
        return self.rules['phases'][self.phase]

    def advance_phase(self):
        if self.prelim < len(self.rules.get('prelim', [])):
            self.prelim += 1
            return
        self.phase = (self.phase + 1) % len(self.rules['phases'])

    def enter_phase(self, srv=None):
        self.notice = None
        phase = self.current_phase
        self.phase_start = time.time()
        self.phase_shift = phase['schedule'].next_time_in_period(delta=time_parse(phase['duration']))
        self.current_phase['handler'].on_entry(srv=srv, game=self)
        self.update_notice(srv=srv)

    def update_notice(self, srv=None):
        notice = Text('{} in the village\n'.format(self.current_phase['name'].upper()))
        notice.append('Still alive:')
        for p in self.players:
            notice.extend((' ', p))
        notice.append('\n')
        notice.append('Dead:')
        for p in self.dead:
            notice.extend((' ', p, ' (', self.roles[p].role.name, ')'))
        notice.append('\n')
        now = time.time()
        running = True
        if self.phase_shift > now:
            notice.extend(('This phase will end at ', time.strftime("%I:%M%p on %A", time.gmtime(self.phase_shift)),

                           ' (', int((self.phase_shift - time.time() + 59) // 60), ' minutes from now)\n'))
        else:
            running = False
            notice.append('This phase has ended\n')

        phase_text = self.current_phase['handler'].notice(game=self, running=running)
        if phase_text is not None:
            notice.extend(phase_text)

        self.notice = srv.post_notice(channel=self.public, notice=self.notice, text=notice)

    def tick(self, srv=None, srv_lookup=None):
        self.update_notice(srv=srv)

        # Possibly, one side has conceded. Hand the victory to the other side.
        if self.winner is not None:
            return DeleteTarget(self),

        # Possibly, end the phase. If so, we may want to stop the game.
        if self.phase_shift > time.time():
            return

        self.winner = self.current_phase['handler'].on_exit(srv=srv, game=self)
        self.update_notice(srv=srv)
        if self.winner:
            notice = Text('Still alive:')
            for p in self.players:
                notice.extend((' ', p, ' (', self.roles[p].role.name, ')'))
            notice.append('\n')
            notice.append('Dead:')
            for p in self.dead:
                notice.extend((' ', p, ' (', self.roles[p].role.name, ')'))
            notice.append('\n')
            notice.extend(("A side emerges victorious: ", self.winner))

            srv.post_notice(channel=self.public, text=notice)
            return DeleteTarget(self),

        # Shift phases
        self.advance_phase()
        self.enter_phase(srv=srv)

    def persist(self):
        if self.winner is None:
            save(self.index, self)
        else:
            drop(self.index)

    def save(self):
        return self

    @classmethod
    def load(cls, value):
        return value
