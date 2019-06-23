from collections import namedtuple


class Channel(namedtuple('Channel', ('id', 'name', 'is_private', 'is_im'), defaults=(None, None, False, False))):
    def replace(self, **kwargs):
        return self._replace(**kwargs)


class Agent(namedtuple('Agent', ('id', 'name', 'is_bot', 'real_name'), defaults=(None, None, False, None))):
    def replace(self, **kwargs):
        return self._replace(**kwargs)


Notice = namedtuple('Notice', ('channel', 'id'))


class BaseService:
    def broadcast(self, channel=None, text=None):
        """Broadcast a message to a channel

        This may return a value (which might be utilised by other Service methods)"""
        raise NotImplementedError()

    def new_channel(self, name=None, private=False, invite=None):
        """Create a new channel and invite users into it

        This returns a serialisable handle to the channel."""
        raise NotImplementedError()

    def delete_channel(self, channel=None):
        """Remove a channel completely"""
        raise NotImplementedError()

    def invite_to_channel(self, channel=None, invite=None):
        """Pull one or more users into a channel

        The bot user associated with this service may need to be in the invite list.
        Passing `None` is harmless."""
        raise NotImplementedError()

    def lookup_channel(self, channel=None):
        """Given a channel, fill in any missing details from its description"""
        raise NotImplementedError()

    def lookup_user(self, agent=None):
        """Given an Agent, fill in any missing details from its description"""
        raise NotImplementedError()

    def oauth_uri(self, scope=None, state=None):
        """Compute a service handoff URI that a user may use to deliver an oauth token to the application"""
        raise NotImplementedError()

    def oauth_complete(self, code=None):
        """Given an oauth return, finish the handshake to recover the oauth token"""
        raise NotImplementedError()

    def post_notice(self, channel=None, notice=None, text=None):
        """Post or update a notice in a channel

        Implementations may vary in how they deal with this. Note, this may be called quite frequently,
        so it should not simply spam a channel with non-updates.

        It should return a Notice, which will identify the notice/pinned message, as applicable."""
        raise NotImplementedError()

    def delete_message(self, channel=None, message_id=None):
        """Remove a message from a channel

        Assuming that's possible."""
        raise NotImplementedError()

    def whisper(self, channel=None, agent=None, text=None):
        """Deliver a message to a single user, within a channel"""
        raise NotImplementedError()