from collections import namedtuple
import logging
from recordtype import recordtype
import threading
from .persist import load, save
from .text import Text


LOG = logging.getLogger(__name__)


class BaseDispatch:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def raw_message(self, srv=None, sender=None, receivers=None, channel=None, text=None, message_id=None):
        LOG.debug("Just received a message from %s to %s: %r", sender, channel, text)

    def on_message(self, srv=None, sender=None, receivers=None, channel=None, text=None):
        LOG.debug("Just received a message from %s to %s: %r", sender, channel, text)

    def oauth_callback(self, srv=None, code=None, state=None):
        LOG.debug("Just received an oauth callback state=%s code=%s to %s: %r", state, code)

    def tick(self, srv=None, srv_lookup=None):
        LOG.debug("Time passes")


QueuedOnMessage = recordtype('QueuedOnMessage', ('srv', 'sender', 'receivers', 'channel', 'text', 'message_id'))
QueuedOauthCallback = recordtype('QueuedOauthCallback', ('srv', 'code', 'state'))
QueuedTick = recordtype('QueuedTick', ('srv', 'srv_lookup',))


class QueuingDispatch(BaseDispatch):
    def __init__(self, queue=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue

    def raw_message(self, srv=None, sender=None, receivers=None, channel=None, text=None, message_id=None):
        self.queue.put(QueuedOnMessage(srv, sender, receivers, channel, text, message_id), timeout=1)

    def oauth_callback(self, srv=None, code=None, state=None):
        self.queue.put(QueuedOauthCallback(srv, code, state), timeout=1)

    def tick(self, srv=None, srv_lookup=None):
        self.queue.put(QueuedTick(srv, srv_lookup), timeout=1)


class DequeuingDispatch(BaseDispatch, threading.Thread):
    def __init__(self, queue=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue
        self.thread = threading.Thread()

    def run(self):
        while True:
            try:
                m = self.queue.get()
                if isinstance(m, QueuedOnMessage):
                    # Resolve names
                    m.sender = m.srv.lookup_user(m.sender)
                    m.receivers = [m.srv.lookup_user(rcv) for rcv in m.receivers]
                    m.channel = m.srv.lookup_channel(m.channel)
                    # Parse text into a rope of items
                    m.text = Text.parse(m.text, srv=m.srv)
                    m.text.message_id = m.message_id
                    self.on_message(srv=m.srv, sender=m.sender, receivers=m.receivers, channel=m.channel, text=m.text)
                elif isinstance(m, QueuedOauthCallback):
                    self.oauth_callback(srv=m.srv, code=m.code, state=m.state)
                elif isinstance(m, QueuedTick):
                    self.tick(srv=m.srv, srv_lookup=m.srv_lookup)
            except Exception:
                LOG.exception('Problem handling queued message')

            finally:
                self.queue.task_done()


NewTarget = namedtuple('NewTarget', ('handler', 'channels'))
DeleteTarget = namedtuple('DeleteTarget', ('handler',))


class MuxDispatch(DequeuingDispatch):
    def __init__(self, default=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_map = {}
        self.target_map = {}
        self.default = default

    def on_message(self, srv=None, sender=None, receivers=None, channel=None, text=None):
        target = self.channel_map.get(channel, self.default)
        result = target.on_message(srv=srv, sender=sender, receivers=receivers, channel=channel, text=text)

        # Process the result
        self.process(result)
        target.persist()

    def oauth_callback(self, srv=None, code=None, state=None):
        result = self.default.oauth_callback(srv=srv, code=code, state=state)
        self.process(result)

    def tick(self, srv=None, srv_lookup=None):
        self.process(self.default.tick(srv=srv))
        self.default.persist()
        # Dispatch the tick to everyone
        for target in list(self.target_map):
            srv = srv_lookup(target.team)
            if srv is not None:
                self.process(target.tick(srv=srv))
                target.persist()

    def process(self, response):
        if response is None:
            return
        for item in response:
            if callable(item):
                LOG.info("administrative callback running")
                item(self)
            elif isinstance(item, NewTarget):
                LOG.debug('Registering new handler, %s, for %s', item.handler, item.channels)
                self.target_map[item.handler] = item.channels
                for c in item.channels:
                    self.channel_map[c] = item.handler
                item.handler.persist()
            elif isinstance(item, DeleteTarget):
                channels = self.target_map.pop(item.handler)
                LOG.debug('Unregistering handler, %s, for %s', item.handler, channels)
                for c in channels:
                    del self.channel_map[c]
            else:
                LOG.warning('Unknown response from message: %s', item)
        self.persist()

    def persist(self):
        save('mux', self)

    def save(self):
        return [{'target': target.index, 'channels': channels} for target, channels in self.target_map.items()]

    @classmethod
    def load(cls, value, default_type=None, default_factory=None, target_factory=None, **kwargs):
        """This load method will drive the reload or reconstruction of everything"""
        default = load('default', default=default_type, factory=default_factory)
        loaded = cls(default=default, **kwargs)  # Pass through the queue
        target_map = {}
        channel_map = {}
        for item in value:
            target = load(item['target'], default=lambda: None, factory=target_factory)
            if target is not None:
                channels = item['channels']
                target_map[target] = channels
                for channel in channels:
                    channel_map[channel] = target
        loaded.target_map = target_map
        loaded.channel_map = channel_map
        return loaded
