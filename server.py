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


ROOM_NAME_LENGTH = 4

_rooms = {}
_room_lock = threading.Lock()


class User(object):
    def __init__(self, user_id, conn_id):
        self.user_id = user_id
        self.conn_id = conn_id

    def __str__(self):
        return 'USER: id -> %s, conn: %s' % (self.user_id, self.conn_id)


class Room(object):
    def __init__(self, name):
        self.name = name
        self.content = ''  # 服务器保存内容
        self.users_content = {}  # key: 用户UUID, value: 用户看到的内容
        self.dmp = diff_match_patch_py3.diff_match_patch()
        self.users = []  # 一个浏览器窗口算作一个user

    def __str__(self):
        users_desc = [str(user) for user in self.users]
        return 'ROOM: %s\ncontent: %s\nusers_content: %s\nusers: %s' % (
            self.name, self.content, self.users_content, str(users_desc))

    def update(self, uid, patch):
        if uid not in self.users_content:
            self.users_content[uid] = ''
        if patch is not None:
            patch = self.dmp.patch_fromText(patch)
            user_content = self.users_content[uid]
            self.content = self.apply_patch(patch, self.content)  # 更新服务器内容
            new_patch = self.generate_patch(user_content, self.content)  # 比较服务器与用户内容差异
        else:
            new_patch = self.generate_patch('', self.content)
        self.users_content[uid] = self.content  # 用户内容更新
        return self.dmp.patch_toText(new_patch)  # 返回差异patch

    def apply_patch(self, patch, string):
        x = self.dmp.patch_apply(patch, string)
        return x[0]  # 返回新字符串

    def generate_patch(self, string1, string2):
        diff = self.dmp.diff_main(string1, string2)
        patch = self.dmp.patch_make(string1, diff)
        return patch


class PatchUpdater(tornado.web.RequestHandler):
    def post(self, *args, **kwargs):
        try:
            body = json.loads(self.request.body.decode('utf-8'))
            input_uid = body.get('uid')
            input_patch = body.get('patch')
            input_room = body.get('room')
            if not input_uid or not input_room:
                raise Exception(str(body))
        except Exception as e:
            raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)

        room = get_room(input_room)
        patch = room.update(input_uid, input_patch)
        self.write(json.dumps(patch))


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
        if message.startswith('----handshake----\n'):
            handshake_data = json.loads(message.split('\n')[1])
            room = get_room(handshake_data['room'])     # room should have been created
            user_id = handshake_data['user_id']
            user_obj = User(user_id, hash(self))
            room.users.append(user_obj)
            self.write_message(message)
        else:
            try:
                body = json.loads(message)
                input_uid = body.get('uid')
                input_patch = body.get('patch')
                input_room = body.get('room')
                if not input_uid or not input_room:
                    raise Exception(str(body))
            except Exception as e:
                raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)

            room = get_room(input_room)
            patch = room.update(input_uid, input_patch)
            self.write_message(json.dumps(patch))
            # self.ping("123 ping".encode('utf-8'))
            # print('----', self.ws_connection)

    def on_close(self):
        print("WebSocket closed")
        room, index = find_user_by_connection(hash(self))
        room.users.pop(index)
        with _room_lock:
            empty_room_key = None
            for key, room in _rooms.items():
                if len(room.users) == 0:
                    empty_room_key = key
            if empty_room_key is not None:
                _rooms.pop(empty_room_key)

    def on_pong(self, data):
        print('on pong', data)


def find_user_by_connection(conn_id):
    """
    :param conn_id:
    :return: user's room, index of the room's users list
    """
    with _room_lock:
        for _, room in _rooms.items():
            for index, user in enumerate(room.users):
                if user.conn_id == conn_id:
                    return room, index


def get_room(name):
    with _room_lock:
        return _rooms.get(name)


def room_exists(name):
    with _room_lock:
        return name in _rooms


def find_free_room(also_create=True):
    chars = string.ascii_letters + string.digits
    retries = int(pow(ROOM_NAME_LENGTH, len(chars)) / 2)
    with _room_lock:
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
            (r"/api/update", PatchUpdater),
            (r'/[A-Za-z0-9]+([\?/].*)?', RoomPage),
        ],
        template_path=config.TEMPLATE_FILE_PATH,
        static_path=config.STATIC_FILE_PATH,
        cookie_secret="x",
        xsrf_cookies=False,
        autoreload=False,
        debug=False,
        websocket_ping_interval=0,
    )


def monitor_rooms():
    def f():
        while True:
            time.sleep(120)
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
