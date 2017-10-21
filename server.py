#!/usr/bin/env python3
# coding=utf-8
import json
import diff_match_patch_py3
import tornado.ioloop
import tornado.web
import tornado.httpserver
import config


class Server(object):
    def __init__(self):
        self.content = ''  # 服务器保存内容
        self.users_content = {}  # key: 用户ID, value: 用户看到的内容
        self.dmp = diff_match_patch_py3.diff_match_patch()

    def update(self, uid, diff):
        if uid not in self.users_content:
            self.users_content[uid] = ''
        if diff is not None:
            user_content = self.users_content[uid]
            self.content = self.diff_apply_to_string(diff, self.content)  # 更新服务器内容
            new_diff = self.generate_diff(user_content, self.content)  # 比较服务器与用户内容差异
        else:
            new_diff = self.generate_diff('', self.content)
        self.users_content[uid] = self.content  # 用户内容更新
        print('content', self.content)

        return new_diff  # 返回最新的差异

    def diff_apply_to_string(self, diff, string):
        p = self.dmp.patch_make(string, diff)
        x = self.dmp.patch_apply(p, string)
        return x[0]

    def generate_diff(self, string1, string2):
        return self.dmp.diff_main(string1, string2)


class Handler(tornado.web.RequestHandler):
    def post(self, *args, **kwargs):
        try:
            body = json.loads(self.request.body)
            if 'uid' not in body:
                raise
            if 'diff' not in body:
                raise
        except Exception as e:
            raise tornado.web.HTTPError(400, 'Invalid params: %s' % e)
        server = get_server()
        diff = server.update(body['uid'], body['diff'])
        self.write(json.dumps(diff))

    def get(self, *args, **kwargs):
        self.write(get_server().content)


class MainPage(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        self.render("main.html")

_server = None


def get_server():
    global _server
    if _server is None:
        _server = Server()
    return _server


def make_app():
    return tornado.web.Application(
        [
            (r"/main", MainPage),
            (r"/.+", Handler),
        ],
        template_path=config.TEMPLATE_FILE_PATH,
        static_path=config.STATIC_FILE_PATH,
        cookie_secret="xxxxxxx",
        xsrf_cookies=False,
        debug=False
    )


if __name__ == "__main__":
    app = make_app()
    srv = tornado.httpserver.HTTPServer(app, xheaders=True)
    srv.bind(config.PORT)
    srv.start()
    tornado.ioloop.IOLoop.instance().start()
