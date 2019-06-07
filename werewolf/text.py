import html
import logging
import re
from .sentinel import Sentinel
from .service import Agent, Channel

LOG = logging.getLogger(__name__)


class Text(list):
    SPLITTER = re.compile(r'(<(?:@\w+|#\w+\|[^>]*)>)')
    AGENT = re.compile(r'^<@(\w+)>$')
    CHANNEL = re.compile(r'^<#(\w+)\|[^>]*>$')

    def __init__(self, *rope):
        super().__init__(rope)

    @classmethod
    def parse(cls, text, srv=None):
        rope = [cls.resolve(i, srv=srv) for i in Text.SPLITTER.split(text)]
        return cls(*rope)

    @staticmethod
    def resolve(item, srv=None):
        if isinstance(item, str):
            agent = Text.AGENT.fullmatch(item)
            if agent is not None:
                agent = Agent(id=agent.group(1))
                if srv is not None:
                    agent = srv.lookup_user(agent)
                return agent
            channel = Text.CHANNEL.fullmatch(item)
            if channel is not None:
                channel = Channel(id=channel.group(1))
                if srv is not None:
                    channel = srv.lookup_channel(channel)
                return channel
            return html.unescape(item)
        elif isinstance(item, Agent):
            return srv.lookup_user(item)
        elif isinstance(item, Channel):
            return srv.lookup_channel(item)
        return item

    def __str__(self):
        return ''.join(self.render(item) for item in self)

    @staticmethod
    def render(item, srv=None):
        if isinstance(item, str):
            return html.escape(item, quote=False)
        elif isinstance(item, Agent):
            return '<@{}>'.format(item.id)
        elif isinstance(item, Channel):
            return '<#{}>'.format(item.id)
        return str(item)

    def split(self):
        """Trim and split every text entry"""
        rope = []
        for item in self:
            if isinstance(item, str):
                rope.extend(item.split())
            else:
                rope.append(item)
        return Text(*rope)

    def match(self, *pattern):
        LOG.debug("matching %r against %r", self, pattern)
        result = []
        index = 0
        for item in pattern:
            LOG.debug("item is %r at %d", item, index)
            if isinstance(item, str):
                if index < len(self) and self[index] == item:
                    LOG.debug("word matches: %s", item)
                    index += 1
                    continue
                else:
                    return None
            elif isinstance(item, list) and len(item) == 1:
                if callable(item[0]) and not isinstance(item[0], type):
                    m = item[0]
                else:
                    m = lambda thing: thing if isinstance(thing, item[0]) else None
                LOG.debug("scanning for sequence of type %r", m)
                output = []
                result.append(output)
                while index < len(self):
                    ans = m(self[index])
                    if ans is not None:
                        output.append(ans)
                        index += 1
                    else:
                        break
                continue
            elif isinstance(item, Agent):
                LOG.debug("scanning for specific agent %s", item)
                if index < len(self) and self[index] == item:
                    index += 1
                    continue
                else:
                    return None
            elif isinstance(item, type):
                LOG.debug("matching single thing of type %r", item)
                if index < len(self) and isinstance(self[index], item):
                    result.append(self[index])
                    index += 1
                    continue
                else:
                    return None
            elif callable(item):
                LOG.debug("using matcher function for a single thing: %r", item)
                if index < len(self):
                    ans = item(self[index])
                    if ans is not None:
                        result.append(ans)
                        index += 1
                        continue
                return None
            else:
                LOG.debug("no idea how to match %r", item)
                return None
        if index == len(self):
            LOG.debug("match reaches end of input - returning %r", result)
            return result
        return None

    def __add__(self, other):
        return Text(*super().__add__(other))


def reg():
    def decorate(*match):
        def dec(f):
            decorate.decorated.append((match, f))
            return f
        return dec
    decorate.decorated = []
    decorate.me = Sentinel('me')

    return decorate
