#!/usr/bin/env python3
# coding=utf-8
import json
import uuid
import time
import diff_match_patch_py3
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import config
import threading
import string
import random
import urllib


ROOM_NAME_LENGTH = 4

_rooms = {}
_op_lock = threading.Lock()


class Room(object):
    def __init__(self, name):
        self.name = name
        self.content = ''  # 服务器保存内容
        self.dmp = diff_match_patch_py3.diff_match_patch()
        self.users = {}  # 一个浏览器窗口算作一个user, key: user_id, value: websocket

    def __str__(self):
        return 'ROOM: %s\ncontent: %s\nusers: %s' % (self.name, self.content, self.users)

    def apply_patch(self, patch, old_string):
        x = self.dmp.patch_apply(patch, old_string)
        new_string = x[0]
        return new_string  # 返回新字符串

    def generate_patch(self, old_string, new_string):
        diff = self.dmp.diff_main(old_string, new_string)
        patch = self.dmp.patch_make(old_string, diff)
        return patch

    def broadcast(self, user_id, input_patch_text):
        patch = self.dmp.patch_fromText(input_patch_text)
        self.content = self.apply_patch(patch, self.content)  # 更新服务器内容

        for uid, websocket in self.users.items():
            if uid == user_id:
                continue
            websocket.write_message(json.dumps(input_patch_text))


class WelcomePage(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        self.render('welcome.html')

    def post(self, *args, **kwargs):
        is_new_room = True
        try:
            self.get_argument('old')
            is_new_room = False
        except tornado.web.MissingArgumentError:
            pass
        if is_new_room:
            _ = self.get_argument('new')
            name = find_free_room(also_create=True)
            if name is None:
                raise tornado.web.HTTPError(404, "Rooms are full")
        else:
            name = self.get_argument('room_name')
            ok = room_exists(name)
            if not ok:
                raise tornado.web.HTTPError(404, "Room not found")
        self.redirect('/%s' % name)


class RoomPage(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        room_name = self.request.path
        if room_name.startswith('/'):
            room_name = room_name[1:]
        assert len(room_name) > 0
        room = get_room(room_name)
        if room is None:
            raise tornado.web.HTTPError(404, 'Room not exists')
        user_id = str(uuid.uuid4())
        self.render('main.html', user_id=user_id, room=room_name)


# The WebSocket Protocol - https://tools.ietf.org/html/rfc6455
class WebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        handshake_symbol = '----handshake----\n'
        if message.startswith(handshake_symbol):
            data = json.loads(message.split('\n')[1])
            room = _rooms.get(data['room'])  # room should have been created

            with _op_lock:
                room.users[data['user_id']] = self
                data['content'] = room.content

            self.write_message(handshake_symbol + json.dumps(data))
        else:
            try:
                body = json.loads(message)
                input_uid = body.get('uid')
                input_patch_text = body.get('patch')
                input_room = body.get('room')
                if not input_uid or not input_room:
                    raise Exception(str(body))
            except Exception as e:
                raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)

            room = _rooms[input_room]
            room.broadcast(input_uid, input_patch_text)

    def on_close(self):
        user_exit_room(self)
        print("WebSocket closed")

    def check_origin(self, origin):
        parsed_origin = urllib.parse.urlparse(origin)
        return parsed_origin.netloc.endswith(".pood.xyz")


def get_room(name):
    with _op_lock:
        return _rooms.get(name)


def room_exists(name):
    with _op_lock:
        return name in _rooms


def user_exit_room(user_websocket):
    target_room = None
    target_uid = None
    with _op_lock:
        for _, room in _rooms.items():
            if target_room is not None:
                break
            for uid, socket in room.users.items():
                if socket == user_websocket:
                    target_uid = uid
                    target_room = room
                    break
        target_room.users.pop(target_uid)


def find_free_room(also_create=True):
    chars = string.ascii_letters + string.digits
    retries = int(pow(ROOM_NAME_LENGTH, len(chars)) / 2)
    with _op_lock:
        for i in range(retries):
            name = ''.join(random.choice(chars) for _ in range(ROOM_NAME_LENGTH))
            if name not in _rooms:
                if also_create:
                    _rooms[name] = Room(name)
                return name
    return None


def make_app():
    return tornado.web.Application(
        [
            (r"/", WelcomePage),
            (r"/api/websocket", WebSocket),
            (r'/[A-Za-z0-9]+([\?/].*)?', RoomPage),
        ],
        template_path=config.TEMPLATE_FILE_PATH,
        static_path=config.STATIC_FILE_PATH,
        cookie_secret="x",
        xsrf_cookies=False,
        autoreload=False,
        debug=False,
        websocket_ping_interval=10,
        websocket_ping_timeout=60,
    )


def monitor_rooms():
    def f():
        while True:
            time.sleep(20)
            for _, room in _rooms.items():
                print(room)

    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()


if __name__ == "__main__":
    app = make_app()
    srv = tornado.httpserver.HTTPServer(app, xheaders=True)
    srv.bind(config.PORT)
    srv.start()
    monitor_rooms()
    tornado.ioloop.IOLoop.instance().start()
