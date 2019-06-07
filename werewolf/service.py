from base64 import b64encode as b64
import cachetools
from collections import namedtuple
import logging
import os
import requests
import urllib.parse
import yaml
from .sentinel import Sentinel


LOG = logging.getLogger(__name__)

CONFIG = None
SERVICE_CONFIG = {}
SERVICES = {}
TOKENS = None


def load_config():
    global CONFIG, SERVICE_CONFIG, TOKENS
    CONFIG = os.environ['CONFIG']
    with open(CONFIG) as f:
        SERVICE_CONFIG = yaml.safe_load(f)

    TOKENS = set()
    teams = SERVICE_CONFIG['teams']
    for team in teams:
        config = teams[team]
        SERVICES[team] = Service(team=team, config=config)
        TOKENS.add(config['token'])


def get_service(team=None):
    return SERVICES.get(team)


def validate_token(token):
    return token in TOKENS


class Channel(namedtuple('Channel', ('id', 'name', 'is_private', 'is_im'), defaults=(None, None, False, False))):
    def replace(self, **kwargs):
        return self._replace(**kwargs)


class Agent(namedtuple('Agent', ('id', 'name', 'is_bot', 'real_name'), defaults=(None, None, False, None))):
    def replace(self, **kwargs):
        return self._replace(**kwargs)


Notice = namedtuple('Notice', ('channel', 'id'))


class Service:
    IM_PLACEHOLDER = Sentinel("(im)")
    OAUTH_HANDOFF = 'https://slack.com/oauth/authorize'
    OAUTH_ACCESS = 'https://slack.com/api/oauth.access'

    def __init__(self, *args, team=None, config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.token = config['token']
        self.bot = config['bot-oauth']
        self.user = config['oauth']
        self.client_id = config['client-id']
        self.client_secret = config['client-secret']
        self.oauth_base_uri = config['oauth-uri']
        self._user_cache = cachetools.TTLCache(maxsize=1024, ttl=600)
        self._channel_cache = cachetools.TTLCache(maxsize=1024, ttl=600)
        self.session = requests.Session()

    def get(self, *args, **kwargs):
        return self.session.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self.session.post(*args, **kwargs)

    @staticmethod
    def json(resp):
        j = resp.json()
        if resp.status_code != 200 or not j.get('ok'):
            raise RuntimeError(j.get('error'))
        return j

    def broadcast(self, channel=None, text=None):
        LOG.debug("Broadcasting to %s: %r", channel, text)
        resp = self.post('https://slack.com/api/chat.postMessage',
                         headers={'Authorization': 'Bearer {}'.format(self.bot)},
                         json={"text": str(text), "channel": channel.id})
        return self.json(resp)

    def new_channel(self, name=None, private=False, invite=None):
        LOG.debug("Constructing new channel: %s for %s", name, invite)

        resp = self.post('https://slack.com/api/conversations.create',
                         headers={'Authorization': 'Bearer {}'.format(self.user)},
                         json={'name': name, 'is_private': private, 'user_ids': [user.id for user in invite]})
        j = self.json(resp)

        channel = Channel(id=j.get('channel', {}).get('id'),
                          name=j.get('channel', {}).get('name'),
                          is_private=j.get('channel', {}).get('is_private', False))
        LOG.info("channel created: %s", channel)

        # Invite the users to the channel
        self.invite_to_channel(channel=channel, invite=invite)

        # The high-privileged user must leave the channel
        resp = self.post('https://slack.com/api/conversations.leave',
                         headers={'Authorization': 'Bearer {}'.format(self.user)},
                         json={'channel': channel.id})
        self.json(resp)

        return channel

    def delete_channel(self, channel=None):
        LOG.debug("Deleting channel: %s", channel)

        if channel.is_im:
            resp = self.post('https://slack.com/api/conversations.close',
                             headers={'Authorization': 'Bearer {}'.format(self.user)},
                             json={'channel': channel.id})
        elif channel.is_private:
            resp = self.post('https://slack.com/api/groups.delete',
                             headers={'Authorization': 'Bearer {}'.format(self.user)},
                             json={'channel': channel.id})
        else:
            resp = self.post('https://slack.com/api/channels.delete',
                             headers={'Authorization': 'Bearer {}'.format(self.user)},
                             json={'channel': channel.id})
        j = self.json(resp)
        LOG.debug("Channel delete responds with %s", j)

    def invite_to_channel(self, channel=None, invite=None):
        if invite is not None:
            resp = self.post('https://slack.com/api/conversations.invite',
                             headers={'Authorization': 'Bearer {}'.format(self.user)},
                             json={'channel': channel.id, 'users': ','.join(user.id for user in invite)})
            self.json(resp)
        return

    def lookup_channel(self, channel=None):
        LOG.debug("Looking up channel details: %s", channel)
        if channel.name is not None:
            return channel
        name = self._channel_cache.get(channel.id)
        if name is not None:
            channel = channel.replace(name=name)
            LOG.debug('Cache finds channel id %s with name %s', channel.id, channel.name)
            return channel
        # Do the lookup
        try:
            resp = self.get('https://slack.com/api/conversations.info',
                            params={'channel': channel.id},
                            headers={'Authorization': 'Bearer {}'.format(self.bot)})
            if resp.status_code == 200:
                j = resp.json()
                if j.get('ok'):
                    if j.get('channel', {}).get('is_im', False):
                        channel = channel.replace(name=Service.IM_PLACEHOLDER)
                    else:
                        channel = channel.replace(name=j.get('channel', {}).get('name'))
                    self._channel_cache[channel.id] = channel.name
                    LOG.debug('Cache records channel id %s with name %s', channel.id, channel.name)
                    return channel

        except Exception as e:
            LOG.error('Problem looking up channel name: %s', e)

        return channel

    def lookup_user(self, agent=None):
        LOG.debug("Looking up user details: %s", agent)
        if agent.name is not None:
            return agent
        cached = self._user_cache.get(agent.id)
        if cached is not None:
            LOG.debug('Cache finds agent id %s with %s', agent.id, cached)
            return cached
        # Do the lookup
        try:
            resp = self.get('https://slack.com/api/users.info',
                            params={'user': agent.id},
                            headers={'Authorization': 'Bearer {}'.format(self.bot)})
            if resp.status_code == 200:
                j = resp.json()
                if j.get('ok'):
                    agent = agent.replace(name=j.get('user', {}).get('name'),
                                          is_bot=j.get('user', {}).get('is_bot', False),
                                          real_name=j.get('user', {}).get('real_name', ""))

                    self._user_cache[agent.id] = agent
                    LOG.debug('Cache records agent id %s with %s', agent.id, agent)
                    return agent

        except Exception as e:
            LOG.error('Problem looking up user name: %s', e)

        return agent

    def oauth_uri(self, scope=None, state=None):
        return Service.OAUTH_HANDOFF+"?"+urllib.parse.urlencode({'client_id': self.client_id,
                                                                 'scope': scope,
                                                                 'redirect_uri': self.oauth_base_uri + self.team,
                                                                 'state': state,
                                                                 'team': self.team})

    def oauth_complete(self, code=None):
        LOG.debug("completing oauth with code=%s", code)
        auth = 'Basic {}'.format(
            b64(bytes(
                '{}:{}'.format(urllib.parse.quote(self.client_id), urllib.parse.quote(self.client_secret)), 'utf-8')
                ).decode('utf-8'))
        resp = self.post(self.OAUTH_ACCESS,
                         headers={'Authorization': auth},
                         data={'code': code, 'redirect_uri': self.oauth_base_uri + self.team})
        return resp.json()

    def post_notice(self, channel=None, notice=None, text=None):
        if notice is None:
            resp = self.broadcast(channel=channel, text=text)
            notice = Notice(channel, resp['ts'])
            resp = self.post('https://slack.com/api/pins.add',
                             headers={'Authorization': 'Bearer {}'.format(self.bot)},
                             json={"channel": channel.id, "timestamp": notice.id})
            self.json(resp)
            return notice

        assert channel == notice.channel

        LOG.debug("Updating notice to %s: %r", channel, text)
        resp = requests.post('https://slack.com/api/chat.update',
                             headers={'Authorization': 'Bearer {}'.format(self.bot)},
                             json={"text": str(text),
                                   "channel": channel.id,
                                   "ts": notice.id})
        self.json(resp)
        return notice

    def delete_message(self, channel=None, message_id=None):
        resp = requests.post('https://slack.com/api/chat.delete',
                             headers={'Authorization': 'Bearer {}'.format(self.user)},
                             json={"channel": channel.id,
                                   "ts": message_id})
        self.json(resp)

    def whisper(self, channel=None, agent=None, text=None):
        LOG.debug("Broadcasting to %s: %r", channel, text)
        resp = self.post('https://slack.com/api/chat.postEphemeral',
                         headers={'Authorization': 'Bearer {}'.format(self.bot)},
                         json={"text": str(text), "channel": channel.id, "user": agent.id})
        return self.json(resp)
