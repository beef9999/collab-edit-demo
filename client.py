#!/usr/bin/env python
# coding=utf-8
import json
import requests
import diff_match_patch

dmp = diff_match_patch.diff_match_patch()


def diff_apply_to_string(diff, string):
    p = dmp.patch_make(string, diff)
    x = dmp.patch_apply(p, string)
    return x[0]


def generate_diff(string1, string2):
    return dmp.diff_main(string1, string2)


def do_request(uid, diff):
    data = {'uid': uid, 'diff': diff}
    r = requests.post('http://localhost:9527/update', data=json.dumps(data))
    new_diff = json.loads(r.text)
    return new_diff


print 'dmp这个库对非ASCII字符处理有些问题，请勿输入中文'
uid = raw_input('输入 user ID\n')


sync_diff = do_request(uid, None)
sync = diff_apply_to_string(sync_diff, '')
print '从服务器同步，content目前为', sync
content = sync

while True:
    new_content = raw_input('基于前一个content编辑:\n')
    diff = generate_diff(content, new_content)
    new_diff = do_request(uid, diff)
    content = diff_apply_to_string(new_diff, content)
    print 'content目前为', content, '\n'

