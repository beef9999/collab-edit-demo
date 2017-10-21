#!/usr/bin/env python3
# coding=utf-8
import json
import requests
import diff_match_patch_py3
import signal
import config

dmp = diff_match_patch_py3.diff_match_patch()


def apply_patch(patch, string):
    x = dmp.patch_apply(patch, string)
    return x[0]


def generate_patch(string1, string2):
    diff = dmp.diff_main(string1, string2)
    patch = dmp.patch_make(string1, diff)
    return patch


def do_request(uid, patch):
    if patch is not None:
        patch = dmp.patch_toText(patch)
    data = {'uid': uid, 'patch': patch}
    r = requests.post('http://localhost:%d/update' % config.PORT, data=json.dumps(data))
    new_patch = json.loads(r.text)
    return dmp.patch_fromText(new_patch)


def get_latest():
    r = requests.get('http://localhost:%d/latest' % config.PORT)
    return r.text


# print 'dmp这个库对非ASCII字符处理有些问题，请勿输入中文'
uid = input('输入 user ID\n')

sync_patch = do_request(uid, None)
sync = apply_patch(sync_patch, '')
print('从服务器同步，content目前为', sync)
content = sync


def handle_signal(signal, frame):
    latest = get_latest()
    global content
    content = latest
    print('content更新为：', latest)


signal.signal(signal.SIGQUIT, handle_signal)

while True:
    new_content = input('基于前一个content编辑:\n')
    patch = generate_patch(content, new_content)
    new_patch = do_request(uid, patch)
    content = apply_patch(new_patch, content)
    print('content目前为', content, '\n')

