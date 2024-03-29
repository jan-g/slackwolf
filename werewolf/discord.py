import discord
import logging
import queue

from .service import Agent, Channel
from .service.discord import Service, load_config, token
from .dispatch import QueuingDispatch, MuxDispatch
from .game import GeneralWerewolf, SpecificWerewolf
from .persist import load
from .rules import load_games


LOG = logging.getLogger(__name__)

load_config()
load_games()

QUEUE = queue.Queue()
DISPATCHER = QueuingDispatch(queue=QUEUE)
# RUNNER = load('mux',
#               default=partial(MuxDispatch, queue=QUEUE, default=GeneralWerewolf()),
#               factory=partial(MuxDispatch.load, queue=QUEUE,
#                               default_type=GeneralWerewolf,
#                               default_factory=GeneralWerewolf.load,
#                               target_factory=SpecificWerewolf.load))
RUNNER = MuxDispatch(queue=QUEUE, default=GeneralWerewolf())
RUNNER.start()


# Set up logging
logging.basicConfig(level=logging.DEBUG)
# logging.getLogger('werewolf.text').setLevel(logging.INFO)

# @app.before_first_request
# def activate_timer():
#     def tick():
#         while True:
#             LOG.debug("Time marches on")
#             DISPATCHER.tick(srv_lookup=get_service)
#             time.sleep(60)
#
#     threading.Thread(target=tick).start()


def main():
    bot = discord.Client()
    Service.init(client=bot)

    @bot.event
    async def on_ready():
        print("The bot is ready!")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        if message.type == discord.MessageType.default:
            channel = Channel(id=message.channel.id)
            sender = Agent(id=message.author.id)
            receivers = [Agent(id=message.guild.me.id, is_bot=True)]
            text = message.content
            ts = message.id
            LOG.debug("raw message: %r", text)
            DISPATCHER.raw_message(srv=Service(guild=message.guild),
                                   sender=sender, channel=channel, receivers=receivers,
                                   text=text, message_id=ts)

    bot.run(token())


if __name__ == '__main__':
    main()