from collections import defaultdict
import logging
from werewolf.service import Channel, Notice


LOG = logging.getLogger(__name__)

SERVICES = None


def load_config():
    pass


def get_service(team=None):
    global SERVICES
    if SERVICES is None:
        SERVICES = defaultdict(MockService)
    return SERVICES[team]


def validate_token(token):
    return True


class MockService:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_cache = {}
        self._channel_cache = {}
        self.channel_offset = 0
        self._in_channel = defaultdict(set)  # Channel -> {Agent}
        self.message_offset = 0
        self._messages = defaultdict(list)  # Channel -> [Text]

    def broadcast(self, channel=None, text=None):
        self.message_offset += 1
        text.ts = self.message_offset
        text.channel = channel
        for agent in self._in_channel[channel.id]:
            if not hasattr(agent, '_messages'):
                agent._messages = []
            agent._messages.append(text)
        self._messages[channel].append(text)
        print("<{}> -> {}".format(channel.name, text))
        return {'ts': self.message_offset}

    def new_channel(self, name=None, private=False, invite=None):
        self.channel_offset += 1
        channel = Channel(id="CH{}".format(self.channel_offset),
                          name=name,
                          is_private=private)
        self._channel_cache[channel.id] = channel
        LOG.debug("Creating channel: %s", channel)

        # Invite the users to the channel
        self.invite_to_channel(channel=channel, invite=invite)
        return channel

    def delete_channel(self, channel=None):
        LOG.debug("Deleting channel: %s", channel)
        self._channel_cache.pop(channel.id, None)

    def invite_to_channel(self, channel=None, invite=None):
        self._in_channel[channel.id].update(invite)

    def lookup_channel(self, channel=None):
        if channel.id not in self._channel_cache:
            self._channel_cache[channel.id] = channel
        return self._channel_cache[channel.id]

    def lookup_user(self, agent=None):
        return agent

    def oauth_uri(self, scope=None, state=None):
        return None

    def oauth_complete(self, code=None):
        return None

    def post_notice(self, channel=None, notice=None, text=None):
        if notice is None:
            resp = self.broadcast(channel=channel, text=text)
            notice = Notice(channel, resp['ts'])
            return notice

        assert channel == notice.channel

        text.ts = notice.id
        text.channel = channel

        for agent in self._in_channel[channel.id]:
            if not hasattr(agent, '_messages'):
                agent._messages = []
            agent._messages.append(text)

        self._messages[channel].append(text)
        print("<{}> !> {}".format(channel.name, text))
        return notice

    def whisper(self, channel=None, agent=None, text=None):
        self.message_offset += 1
        text.ts = self.message_offset
        text.channel = channel

        assert agent in self._in_channel[channel.id]

        if not hasattr(agent, '_messages'):
            agent._messages = []
        agent._messages.append(text)
        self._messages[channel].append(text)
        print("<{}> :> {} {}".format(channel.name, agent.name, text))
        return {'ts': self.message_offset}
