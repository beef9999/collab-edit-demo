#!/usr/bin/env python3
# coding=utf-8
import json
import diff_match_patch_py3
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import config


class Room(object):
    def __init__(self):
        self.content = ''  # 服务器保存内容
        self.users_content = {}  # key: 用户ID, value: 用户看到的内容
        self.dmp = diff_match_patch_py3.diff_match_patch()

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


class UpdatePatchHandler(tornado.web.RequestHandler):
    def post(self, *args, **kwargs):
        try:
            body = json.loads(self.request.body.decode('utf-8'))
            if 'uid' not in body:
                raise
            if 'patch' not in body:
                raise
        except Exception as e:
            raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)
        server = get_server()
        patch = server.update(body['uid'], body['patch'])
        self.write(json.dumps(patch))

    def get(self, *args, **kwargs):
        self.write(get_server().content)


class MainPage(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        self.render("main.html")


class WebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        try:
            body = json.loads(message)
            if 'uid' not in body:
                raise
            if 'patch' not in body:
                raise
        except Exception as e:
            raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)
        server = get_server()
        patch = server.update(body['uid'], body['patch'])
        self.write_message(json.dumps(patch))

    def on_close(self):
        print("WebSocket closed")


_room = None


def get_server():
    global _room
    if _room is None:
        _room = Room()
    return _room


def make_app():
    return tornado.web.Application(
        [
            (r"/", MainPage),
            (r"/websocket", WebSocket),
            (r"/update", UpdatePatchHandler),
        ],
        template_path=config.TEMPLATE_FILE_PATH,
        static_path=config.STATIC_FILE_PATH,
        cookie_secret="x",
        xsrf_cookies=False,
        autoreload=True,
        debug=False
    )


if __name__ == "__main__":
    app = make_app()
    srv = tornado.httpserver.HTTPServer(app, xheaders=True)
    srv.bind(config.PORT)
    srv.start()
    tornado.ioloop.IOLoop.instance().start()
