#!/usr/bin/env python
"""Simple draft client with websocket for Vainglory."""

import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import json
import secrets
import threading
import time

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from tornado.options import define, options
from tornado import gen
from datetime import datetime

define("port", default=8888, help="run on the given port", type=int)
define("debug", default=False, help="enable or disable debug mode", type=bool)
define("seconds_per_turn", default=30, help="seconds per turn", type=int)
define("bonus_time", default=60, help="seconds of bonus time", type=int)

# TODO make configurable
heroes = [
    'adagio',
    'alpha',
    'ardan',
    'baptiste',
    'baron',
    'blackfeather',
    'catherine',
    'celeste',
    'churnwalker',
    'flicker',
    'fortress',
    'glaive',
    'grace',
    'grumpjaw',
    'gwen',
    'idris',
    'joule',
    'kestrel',
    'koshka',
    'krul',
    'lance',
    'lorelai',
    'lyra',
    'ozo',
    'petal',
    'phinn',
    'reim',
    'reza',
    'ringo',
    'rona',
    'samuel',
    'saw',
    'skaarf',
    'skye',
    'taka',
    'tony',
    'varya',
    'vox',
]

# TODO move to class
key = Fernet.generate_key()
f = Fernet(key)

# TODO move to Redis
draft_states = {}

# TODO consistency with role / side / team
# TODO conistency with message / event / chat
class DraftState():
    def __init__(self, style, team_blue, team_red):
        self.style = style
        self.team_blue = team_blue
        self.team_red = team_red
        self.turn = 0
        self.history = []
        self.counters = {
            '1': {'counter': SecondCounter(), 'bonus': SecondCounter(value=options.bonus_time)},
            '2': {'counter': SecondCounter(), 'bonus': SecondCounter(value=options.bonus_time)}
        }

    def get_team_blue(self):
        return self.team_blue

    def get_team_red(self):
        return self.team_red

    def get_style(self):
        # TODO Remove need of including index
        return self.style

    def get_history(self):
        return self.history

    def get_turn(self):
        return self.turn

    def get_current_team(self):
        return self.style[self.turn]['side']

    def start_counter(self, team, counter='counter'):
        logging.info("STARTING COUNTER FOR TEAM %s", team)
        self.counters[team][counter].start()

    def stop_counter(self, team, counter='counter'):
        logging.info("STOPPING COUNTER FOR TEAM %s", team)
        v = self.counters[team][counter].finish()
        if counter == 'counter':
            self.reset_counter(team)
        else:
            self.reset_counter(team, v)
        return v

    def get_time(self, team, counter='counter'):
        return self.counters[team][counter].peek()

    def has_time_left(self, team, counter='counter'):
        return self.get_time(team, counter) > 0

    def reset_counter(self, team):
        logging.info("RESETTING COUNTER FOR TEAM %s", team)
        self.counters[team]['counter'] = SecondCounter()

    def reset_bonus_counter(self, team, value):
        logging.info("RESETTING COUNTER FOR TEAM %s", team)
        self.counters[team]['bonus'] = SecondCounter(value=value)

    def next_turn(self):
        self.turn += 1

    def update_draft(self, event):
        self.history.append(event)
        self.next_turn()
        if not self.is_ended():
            self.start_counter(self.get_current_team())

    def is_turn(self, team):
        return self.get_current_team() == team

    def is_ended(self):
        return self.turn >= len(self.style)


# TODO change chatsocket to draft socket...
# TODO start draft button -> ajax call to get joined teams
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/draft/([a-zA-Z0-9-_=]*)$", DraftHandler),
            (r"/chatsocket/([a-zA-Z0-9-_=]*)$", ChatSocketHandler),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=options.debug,
        )
        super(Application, self).__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    """
    Main request handler for the root path and for chat rooms.
    """
    def get(self):
        self.render("index.html", heroes=heroes)

    def post(self):
        team_blue = self.get_argument('teamBlue')
        team_red = self.get_argument('teamRed')
        draft = self.get_argument('draftField')

        # TODO foolproofiy / validate beforehand
        style = json.loads(draft)
        room = secrets.token_urlsafe(16)

        string_spec = "{room}|{role}".format(room=room, role='0')
        hash_spec = f.encrypt(str.encode(string_spec))

        string_blue = "{room}|{role}".format(room=room, role='1')
        hash_blue = f.encrypt(str.encode(string_blue))

        string_red = "{room}|{role}".format(room=room, role='2')
        hash_red = f.encrypt(str.encode(string_red))

        if options.debug:
            url = "localhost:"+ str(options.port) + "/draft/{}"
        else:
            url = "https://vaindraft.herokuapp.com/draft/{}"


        if room not in draft_states:
            draft_states[room] = DraftState(style, team_blue, team_red)

        self.render('invite.html', spectators=url.format(hash_spec.decode()), team_blue=url.format(hash_blue.decode()), team_red=url.format(hash_red.decode()))


class DraftHandler(tornado.web.RequestHandler):
    def get(self, hash=None):
        if not hash:
            self.redirect('/')
            return

        # TODO DRY it
        try:
            decrypted = f.decrypt(str.encode(hash)).decode()
        except (InvalidToken) as e:
            self.redirect('/')
            return

        room, role = decrypted.split("|")

        # TODO keep track who joined...
        draft_state = draft_states[room]
        self.render("draft.html", hash=hash, team_blue=draft_state.get_team_blue(), team_red=draft_state.get_team_red(), draft_order=draft_state.get_style(), heroes=heroes)


# TODO timers
# TODO start button
class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    """
    Handler for dealing with websockets. It receives, stores and distributes new messages.
    """
    waiters = {}

    @gen.engine
    def open(self, hash=None):
        """
        Called when socket is opened.
        """

        if not hash:
            self.send_update(self, self.create_message("error", "No room specified"))
            self.close()
            return

        try:
            decrypted = f.decrypt(str.encode(hash)).decode()
        except (InvalidToken) as e:
            self.redirect('/')
            self.close()
            return

        room, role = decrypted.split("|")

        if not room:
            self.send_update(self, self.create_message("error", "No room specified"))
            self.close()
            return

        if not role:
            self.send_update(self, self.create_message("error", "No role specified"))
            self.close()
            return

        self.room = room
        self.role = role
        draft_state = draft_states[room]

        if room in ChatSocketHandler.waiters:
            if role in [client['role'] for client in ChatSocketHandler.waiters[room]]:
                logging.info('Error: Role already specified')
                # TODO specify which roles are limited
                self.send_update(self, self.create_message("error", "Role already specified"))
                self.room = None
                self.close()
            else:
                ChatSocketHandler.waiters[room].append({'waiter': self, 'role': self.role})
                message = draft_state.get_history()
                self.send_update(self, self.create_message("history", message))
        else:
            ChatSocketHandler.waiters[room] = [{'waiter': self, 'role': self.role}]

    @classmethod
    def send_updates(cls, room, message):
        logging.info("sending message to %d waiters in room %s", len(cls.waiters[room]), room)
        logging.info(message)
        for client in cls.waiters[room]:
            try:
                client['waiter'].write_message(message)
            except:
                logging.error("Error sending message", exc_info=True)

    @classmethod
    def send_update(cls, waiter, message):
        logging.info("sending message to waiter %s", waiter)
        logging.info(message)
        try:
            waiter.write_message(message)
        except:
            logging.error("Error sending message", exc_info=True)


    def on_message(self, message):
        """
        Callback when new message received via the socket.
        """
        logging.info('Received new message %r', message)
        # TODO validate message

        draft_state = draft_states[self.room]

        logging.info(draft_state.stop_counter(self.role))

        if not draft_state.is_turn(self.role):
            logging.info('Not your turn')
            self.send_update(self, self.create_message("message", "Not your turn"))
            return

        event = self.create_message("update", message)

        draft_state.update_draft(event)

        event['index'] = draft_state.get_turn()
        self.send_updates(self.room, event)

        if draft_state.is_ended():
            logging.info('Draft has ended')
            self.send_updates(self.room, self.create_message("message", "Draft has ended"))
            self.close()
            return

        draft_states[self.room] = draft_state

    def on_close(self):
        """
        Callback when the socket is closed. Frees up resource related to this socket.
        """
        if not self.room:
            return

        remove_clients = [client for client in self.waiters[self.room] if client['role'] == self.role]
        for client in remove_clients:
            self.waiters[self.room].remove(client)

        if not self.waiters[self.room]:
            del self.waiters[self.room]

    def create_message(self, type, message):
        event = {
            'time': str(datetime.now()),
            'type': type,
            'message': message,
        }
        return event


# TODO implement with observer pattern?
class SecondCounter(threading.Thread):
    '''
    Create a thread object that will do the counting in the background
    '''
    def __init__(self, interval=1, value=options.seconds_per_turn):
        threading.Thread.__init__(self)
        self.interval = interval  # seconds
        self.value = value
        self.alive = False

    def run(self):
        self.alive = True
        while self.alive:
            if self.value > 0:
                time.sleep(self.interval)
                self.value -= self.interval
            else:
                self.finish()

    def peek(self):
        return self.value

    def finish(self):
        self.alive = False
        return self.value


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
