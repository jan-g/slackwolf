import flask
from functools import partial
import logging
import queue
import threading
import time

from .service import Agent, Channel
from .service.slack import load_config, validate_token, get_service
from .dispatch import QueuingDispatch, MuxDispatch
from .game import GeneralWerewolf, SpecificWerewolf
from .persist import load
from .rules import load_games


LOG = logging.getLogger(__name__)

app = flask.Flask(__name__)

load_config()
load_games()

# BOT_MESSAGE = 'bot_message'
BASE_PATH = '/slack/werewolf'


QUEUE = queue.Queue()
DISPATCHER = QueuingDispatch(queue=QUEUE)
RUNNER = load('mux',
              default=partial(MuxDispatch, queue=QUEUE, default=GeneralWerewolf()),
              factory=partial(MuxDispatch.load, queue=QUEUE,
                              default_type=GeneralWerewolf,
                              default_factory=GeneralWerewolf.load,
                              target_factory=SpecificWerewolf.load))
RUNNER.start()


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('werewolf.text').setLevel(logging.INFO)


@app.route(BASE_PATH, methods=['POST'])
def root(*args, **kwargs):
    args = flask.request.json
    token = args.get('token')
    if not validate_token(token):
        return flask.Response('', status=401)

    if args.get('challenge') is not None:
        return flask.Response(args['challenge'], 200)

    team = args.get('team_id')
    if team is None:
        return flask.Response('', status=404)
    service = get_service(team)
    if service is None:
        return flask.Response('', status=404)
    if service.token != token:
        LOG.warning("Mismatch of token to team: %s", args)
        return flask.Response('', status=400)

    if args.get('type') == 'event_callback':
        event = args.get('event', {})

        if event.get('type') == 'app_mention':
            pass
        elif event.get('type') == 'message' and event.get('subtype') is None:
            LOG.debug('args are %s', {k: args[k] for k in args if k != 'token'})

            text = event.get('text', '')
            sender = Agent(id=event.get('user'))
            channel = Channel(id=event.get('channel'))
            ts = event.get('ts')
            if event.get('channel_type') == 'group':
                channel = channel.replace(is_private=True)
            elif event.get('channel_type') == 'im':
                channel = channel.replace(is_im=True)
            receivers = [Agent(id=rcv, is_bot=True) for rcv in args.get('authed_users', [])]
            DISPATCHER.raw_message(srv=service, sender=sender, channel=channel, receivers=receivers,
                                   text=text, message_id=ts)

        else:
            LOG.debug('args are %s', {k: args[k] for k in args if k != 'token'})

    return flask.Response('', 200)


@app.route(BASE_PATH + "/oauth/<team>", methods=['GET'])
def oauth(team):
    args = flask.request.args
    service = get_service(team)
    if service is not None:
        DISPATCHER.oauth_callback(srv=service, code=args['code'], state=args['state'])
    return flask.Response('', 200)


@app.before_first_request
def activate_timer():
    def tick():
        while True:
            LOG.debug("Time marches on")
            DISPATCHER.tick(srv_lookup=get_service)
            time.sleep(60)

    threading.Thread(target=tick).start()


def main():
    app.run(host='0.0.0.0', port=5002)
