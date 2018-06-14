#!/usr/bin/env python
"""Simple draft client with websockets for Vainglory, but more or less usable for whatever draft you want..."""

import json
import logging
import os.path
import secrets
import threading
import time
from datetime import datetime

import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
from cryptography.fernet import Fernet, InvalidToken
from tornado import gen
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)
define("debug", default=False, help="enable or disable debug mode", type=bool)
define("cookie_key", default=secrets.token_urlsafe(32), help="cookie secret key", type=str)

# TODO move to class
key = Fernet.generate_key()
f = Fernet(key)

# TODO move to Redis
draft_states = {}

# TODO consistency with role / side / team
# TODO consistency with blue / red / 1 / 2
# TODO consistency with message / event / chat
# TODO move options / teams to seperate classes
# TODO timers optional
class DraftState():
    def __init__(self, room, style, heroes, team_blue, team_red, seconds_per_turn, bonus_time, background, background_url):
        self.room = room
        self.style = style
        self.heroes = heroes
        self.team_blue = team_blue
        self.team_red = team_red
        self.turn = 0
        self.seconds_per_turn = seconds_per_turn
        self.initial_bonus_time = bonus_time
        self.bonus_time = {
            '1': bonus_time,
            '2': bonus_time,
        }
        self.ready_to_start = False
        self.started = False
        self.join_status = {
            '0': False,
            '1': False,
            '2': False,
        }
        self.history = []
        self.counter = SecondCounter(self.room, self.seconds_per_turn, self.bonus_time[self.get_current_team()], self.get_current_team())
        self.background = background
        self.background_url = background_url

    def get_team_blue(self):
        return self.team_blue

    def get_team_red(self):
        return self.team_red

    def is_joined(self, team):
        return self.join_status[team]

    def has_joined(self, team):
        self.join_status[team] = True
        if team == '0' and self.is_ready():
            self.ready_to_start = True

    def get_join_status(self):
        return self.join_status

    def get_heroes(self):
        return self.heroes

    def get_style(self):
        # TODO Remove need of including index
        return self.style

    def get_history(self):
        return self.history

    def get_turn(self):
        return self.turn

    def get_current_team(self):
        return self.style[self.turn]['side']

    def start_counter(self):
        tornado.ioloop.IOLoop.current().spawn_callback(lambda: self.counter.loop())

    def stop_counter(self):
        v = self.counter.finish()
        if v['type'] == 'bonus':
            self.bonus_time[v['team']] = v['value']
        return v

    def reset_counter(self):
        self.counter = SecondCounter(self.room, self.seconds_per_turn, self.bonus_time[self.get_current_team()], self.get_current_team())

    def next_turn(self):
        self.turn += 1

    def update_draft(self, event):
        self.history.append(event)
        self.next_turn()

        if not self.is_ended():
            self.reset_counter()
            self.start_counter()

    def is_ready(self):
        return self.is_joined('1') and self.is_joined('2')

    def is_ready_to_start(self):
        return self.ready_to_start

    def is_started(self):
        return self.started

    def has_started(self):
        self.started = True

    def is_turn(self, team):
        return self.get_current_team() == team

    def is_ended(self):
        return self.turn >= len(self.style)


# TODO change chatsocket to draft socket...
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/theme", CookieHandler),
            (r"/draft/([a-zA-Z0-9-_=]*)$", DraftHandler),
            (r"/draftstatus/([a-zA-Z0-9-_=]*)$", DraftStatusHandler),
            (r"/chatsocket/([a-zA-Z0-9-_=]*)$", ChatSocketHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret=options.cookie_key,
            xsrf_cookies=True,
            debug=options.debug,
        )
        super(Application, self).__init__(handlers, **settings)

class CustomHandler(tornado.web.RequestHandler):
    def get_theme(self):
        if not self.get_secure_cookie("theme_cookie"):
            return False
        else:
            return True if self.get_secure_cookie("theme_cookie").decode() == "dark" else False

class MainHandler(CustomHandler):
    """
    Main request handler for the root path and for draft creation post request.
    """
    def get(self):
        self.render("index.html", dark=self.get_theme())

    def post(self):
        # TODO provide defaults
        team_blue = self.get_argument('teamBlue')
        team_red = self.get_argument('teamRed')
        seconds_per_turn = self.get_argument('secondsPerTurn')
        bonus_time = self.get_argument('bonusTime')
        draft = self.get_argument('draftField')
        heroesField = self.get_argument('heroesField')
        background = self.get_argument('customBackground', 'off')
        background_url = self.get_argument('customBackgroundField')

        logging.info(background)
        logging.info(background_url)

        # TODO foolproofiy / validate beforehand
        style = json.loads(draft)
        heroes = json.loads(heroesField)
        room = secrets.token_urlsafe(16)

        # TODO DRY it
        string_admin = "{room}|{role}".format(room=room, role='0')
        hash_admin = f.encrypt(str.encode(string_admin))

        string_blue = "{room}|{role}".format(room=room, role='1')
        hash_blue = f.encrypt(str.encode(string_blue))

        string_red = "{room}|{role}".format(room=room, role='2')
        hash_red = f.encrypt(str.encode(string_red))

        string_spec = "{room}|{role}".format(room=room, role='spec')
        hash_spec = f.encrypt(str.encode(string_spec))

        url = self.request.protocol + "://" + self.request.host + "/draft/{}"

        if room not in draft_states:
            draft_states[room] = DraftState(room, style, heroes, team_blue, team_red, int(seconds_per_turn), int(bonus_time), background, background_url)

        self.render('invite.html', dark=self.get_theme(), room=room, admin=url.format(hash_admin.decode()), spectators=url.format(hash_spec.decode()), team_blue=url.format(hash_blue.decode()), team_red=url.format(hash_red.decode()))


class CookieHandler(tornado.web.RequestHandler):
    """
    Endpoint to change the theme color.
    """
    def get(self):
        theme = self.read()
        if theme == "dark":
            self.set("light")
        else:
            self.set("dark")

    def read(self):
        if self.get_secure_cookie("theme_cookie"):
            return self.get_secure_cookie("theme_cookie").decode()


    def set(self, theme):
        logging.info('Set theme cookie to %s', theme)
        self.set_secure_cookie("theme_cookie", theme, path="/")


class DraftStatusHandler(tornado.web.RequestHandler):
    """
    Endpoint to request status of a draft.
    """
    def get(self, room=None):
        if not room:
            self.redirect('/')
            return

        if room not in draft_states:
            self.redirect('/')
            return

        draft_state = draft_states[room]
        response = draft_state.get_join_status()
        response['ready'] = draft_state.is_ready()
        self.write(response)


class DraftHandler(CustomHandler):
    """
    Handler to generate the draft page.
    """
    def get(self, hash=None):
        if not hash:
            self.redirect('/')
            return

        # TODO DRY it
        try:
            decrypted = f.decrypt(str.encode(hash)).decode()
        except (InvalidToken) as e:
            logging.error(e)
            self.redirect('/')
            return

        room, role = decrypted.split("|")
        draft_state = draft_states[room]
        self.render("draft.html", dark=self.get_theme(), hash=hash, role=role, 
            team_blue=draft_state.get_team_blue(), 
            team_red=draft_state.get_team_red(), 
            draft_order=draft_state.get_style(), 
            heroes=draft_state.get_heroes(), 
            seconds_per_turn = draft_state.seconds_per_turn, 
            bonus_time = draft_state.initial_bonus_time,
            background = draft_state.background,
            background_url = draft_state.background_url
        )


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
            logging.error(e)
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

        draft_state.has_joined(self.role)

        if room in ChatSocketHandler.waiters:
            if (role == '1' or role == '2') and role in [client['role'] for client in ChatSocketHandler.waiters[room]]:
                logging.info('Error: Role already specified')
                self.send_update(self, self.create_message("error", "Role already specified"))
                self.room = None
                self.close()
            else:
                ChatSocketHandler.waiters[room].append({'waiter': self, 'role': self.role})
                message = draft_state.get_history()
                self.send_update(self, self.create_message("history", message))

                if draft_state.is_ready_to_start() and not draft_state.is_started():
                    draft_state.has_started()
                    self.send_updates(self.room, self.create_message("start", "Draft has started"))
                    draft_state.start_counter()
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

        # TODO fix this
        if self.role != '1' and self.role != '2':
            return

        draft_state = draft_states[self.room]

        logging.info(draft_state.stop_counter())

        if not draft_state.is_started():
            logging.info('Draft is not yet started')
            self.send_update(self, self.create_message("message", "Draft is not yet started"))
            return

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

        # TODO identify correct spectator to remove
        if self.role == 'spec':
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


class SecondCounter():
    """
    Background thread for counter (called with ioloop.spawn_callback).
    """
    def __init__(self, room, value, bonus, team):
        self.alive = True
        self.room = room
        self.value = value
        self.bonus = bonus
        self.team = team

    @gen.coroutine
    def loop(self):
        while self.alive and self.value > 0:
            nxt = gen.sleep(1)
            self.value -= 1
            yield ChatSocketHandler.send_updates(self.room, {'type': 'time', 'message': self.value})
            yield nxt

        while self.alive and self.bonus > 0:
            nxt = gen.sleep(1)
            self.bonus -= 1
            yield ChatSocketHandler.send_updates(self.room, {'type': 'bonustime', 'message': self.bonus, 'team': self.team})
            yield nxt

        if self.alive:
            ChatSocketHandler.send_updates(self.room, {'type': 'message', 'message': "Time is up!"})

    def finish(self):
        self.alive = False
        if self.value > 0:
            return {'type': 'time', 'value': self.value, 'team': self.team}
        else:
            return {'type': 'bonus', 'value': self.bonus, 'team': self.team}


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
