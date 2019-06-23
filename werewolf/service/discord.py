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
from collections import namedtuple
import discord
import functools
import os
import queue
import yaml

from .base import Agent, Channel, BaseService


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
     def sync(self, **kwargs):
         result_queue = queue.Queue()
         message = Service.ServiceMessage(f, (self,), kwargs, result_queue)
         self.client.loop.call_soon_threadsafe(asyncio.ensure_future, self.queue.put(message))
         return result_queue.get()
     sync._async = f
     return sync


class Service(BaseService):
    ServiceMessage = namedtuple('ServiceMessage', ('method', 'args', 'kwargs', 'result'))

    def __init__(self, client=None, guild=None, *args, **kwargs):
        self.client = client
        self.guild = guild
        self.queue = asyncio.Queue()
        asyncio.ensure_future(self._service_loop())

    async def _service_loop(self):
        while True:
            message = await self.queue.get()
            result = await message.method(*message.args, **message.kwargs)
            message.result.put(result)

    @make_sync
    async def broadcast(self, channel=None, text=None):
        return await channel.send(text)

    @make_sync
    async def new_channel(self, name=None, private=False, invite=None):
        overwrites = {}
        if private:
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                self.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
        channel = await self.guild.make_text_channel(name, overwrites=overwrites)
        await self.invite_to_channel._async(channel=channel, invite=invite)
        return channel

    def delete_channel(self, channel=None):
        pass

    @make_sync
    async def invite_to_channel(self, channel=None, invite=None):
        if invite is None:
            return
        for agent in invite:
            await channel.set_permissions(agent, read_messages=True, send_messages=True)

    def lookup_channel(self, channel=None):
        return channel

    def lookup_user(self, agent=None):
        return agent

    def oauth_uri(self, scope=None, state=None):
        pass

    def oauth_complete(self, code=None):
        pass

    def post_notice(self, channel=None, notice=None, text=None):
        pass

    def delete_message(self, channel=None, message_id=None):
        pass

    def whisper(self, channel=None, agent=None, text=None):
        pass