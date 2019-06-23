"""A BaseService implementation that interoperates with discord

This is a little awkward since the discord api works using asyncio coroutines, whereas the original slack
implementation used synchronous calls.

Due to the performance constraints on a Slack event-stream consumer, the main driver of calls to this
service runs on a work thread (where it consumes events one-at-a-time). It'll therefore make calls to the
Service implementation on that work thread (that is, off of the thread that runs the asyncio event loop).

In order to wake the asyncio loop, we have to prod something into an asyncio.Queue to get messages into
the handler. Responses are delivered to the waiting thread using a traditional queue.Queue. Yuck.
"""

import asyncio
import cachetools
from collections import namedtuple
import discord
import functools
import logging
import os
import queue
import yaml

from .base import Agent, Channel, BaseService

LOG = logging.getLogger(__name__)

CONFIG = None
SERVICE_CONFIG = {}


def load_config():
    global CONFIG, SERVICE_CONFIG, TOKEN
    CONFIG = os.environ.get('CONFIG', 'discord.yaml')
    with open(CONFIG) as f:
        SERVICE_CONFIG = yaml.safe_load(f)


def token():
    return SERVICE_CONFIG['token']


def make_sync(f):
    @functools.wraps(f)
    def sync(self, *args, **kwargs):
        result_queue = queue.Queue()
        kwargs['team'] = self.team
        message = Service.ServiceMessage(f, (self, *args), kwargs, result_queue)
        self.client.loop.call_soon_threadsafe(asyncio.ensure_future, self.queue.put(message))
        return result_queue.get()
    sync._async = f
    return sync


class Service(BaseService):
    ServiceMessage = namedtuple('ServiceMessage', ('method', 'args', 'kwargs', 'result'))
    queue = None

    @classmethod
    def init(cls, client=None):
        cls.queue = asyncio.Queue()
        cls.client = client
        asyncio.ensure_future(cls._service_loop())

    def __init__(self, guild=None, *args, **kwargs):
        self.team = guild
        self._user_cache = cachetools.TTLCache(maxsize=1024, ttl=600)
        self._channel_cache = cachetools.TTLCache(maxsize=1024, ttl=600)

    @classmethod
    async def _service_loop(cls):
        while True:
            message = await cls.queue.get()
            result = await message.method(*message.args, **message.kwargs)
            message.result.put(result)

    @make_sync
    async def broadcast(self, channel=None, text=None, team=None):
        if not hasattr(channel, 'chan'):
            channel = await self.lookup_channel._async(self, channel=channel, team=team)
        return await channel.chan.send(text)

    @make_sync
    async def new_channel(self, name=None, private=False, invite=None, team=None):
        overwrites = {}
        if private:
            overwrites = {
                team.default_role: discord.PermissionOverwrite(read_messages=False),
                team.me: discord.PermissionOverwrite(read_messages=True)
            }
        chan = await team.create_text_channel(name, overwrites=overwrites)
        channel = Channel(id=chan.id, name=chan.name)
        channel.chan = chan
        await self.invite_to_channel._async(self, team=team, channel=channel, invite=invite)
        return channel

    def delete_channel(self, channel=None, team=None):
        pass

    @make_sync
    async def invite_to_channel(self, channel=None, invite=None, team=None):
        if invite is None:
            return
        if not hasattr(channel, 'chan'):
            channel = await self.lookup_channel._async(self, channel=channel, team=team)
        for agent in invite:
            if not hasattr(agent, 'user'):
                agent = await self.lookup_user._async(self, agent=agent, team=team)
            await channel.chan.set_permissions(agent.user, read_messages=True, send_messages=True)

    @make_sync
    async def lookup_channel(self, channel=None, team=None):
        if channel.name is not None:
            return channel
        cid = int(channel.id)
        cached = self._channel_cache.get(cid)
        if cached is not None:
            return cached
        # Do the lookup
        chan = team.get_channel(cid)
        channel = channel.replace(id=cid, name=chan.name)
        channel.chan = chan
        self._channel_cache[channel.id] = channel
        LOG.debug('Cache records channel id %s with name %s', channel.id, channel)
        return channel

    @make_sync
    async def lookup_user(self, agent=None, team=None):
        LOG.debug("Looking up user details: %s", agent)
        if agent.name is not None:
            return agent
        aid = int(agent.id)
        cached = self._user_cache.get(aid)
        if cached is not None:
            LOG.debug('Cache finds agent id %r with %s', aid, cached)
            return cached
        # Do the lookup
        user = team.get_member(aid)
        if user is not None:
            agent = agent.replace(id=aid,
                                  name=user.name,
                                  is_bot=user.bot,
                                  real_name=user.display_name)
            agent.user = user
            self._user_cache[agent.id] = agent
            LOG.debug('Cache records agent id %r with %s', agent.id, agent)
        LOG.debug('Cache miss, and nothing returned for %s', agent)
        return agent

    def oauth_uri(self, scope=None, state=None):
        pass

    def oauth_complete(self, code=None):
        pass

    @make_sync
    async def post_notice(self, channel=None, notice=None, text=None, team=None):
        pass

    @make_sync
    async def delete_message(self, channel=None, message_id=None, team=None):
        pass

    @make_sync
    async def whisper(self, channel=None, agent=None, text=None, team=None):
        pass
