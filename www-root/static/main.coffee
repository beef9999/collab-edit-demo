editor = ace.edit("collab_editor")
editor.setTheme("ace/theme/monokai")
editor.setPrintMarginColumn(120)
editor.$blockScrolling = Infinity
editSession = editor.getSession()
editSession.setMode("ace/mode/python")


HANDSHAKE_SYMBOL = '----handshake----\n'


content = ''
user_id = $("#user_id").text()
room = $("#room").text()
ws = new WebSocket('wss://chat.pood.xyz/api/websocket')
dmp = new diff_match_patch
user_registered = false
sync = false
cursor = null


apply_patch = (patch, str) ->
    x = dmp.patch_apply(patch, str)
    return x[0]


generate_patch = (str1, str2) ->
    diff = dmp.diff_main(str1, str2)
    patch = dmp.patch_make(str1, diff)
    return patch


send_out = ->
    new_content = editSession.getValue()
    if new_content == content
        return
    if sync
        return

    patch = generate_patch(content, new_content)
    patch_text = dmp.patch_toText(patch)
    data = JSON.stringify(
        uid: user_id
        patch: patch_text
        room: room
    )
    ws.send(data)
    content = new_content


websocket_on_message = (evt) ->
    resp = evt.data
    if not user_registered
        if resp.startsWith(HANDSHAKE_SYMBOL)
            resp_data = JSON.parse(resp.split('\n')[1])
            resp_user_id = resp_data['user_id']
            resp_room = resp_data['room']
            if resp_user_id == user_id and resp_room == room
                user_registered = true
                sync = true
                editSession.setValue(resp_data['content'])
                content = resp_data['content']
                sync = false
            else
                window.alert('Server error')

            editor.on 'change', (event) ->
                send_out()

    else
        input_patch_text = JSON.parse(resp)
        patch = dmp.patch_fromText(input_patch_text)
        new_content = apply_patch(patch, content)

        if new_content != content
            sync = true
            cursor = editor.getCursorPosition()
            editSession.setValue(new_content)
            editor.navigateTo(cursor.row, cursor.column)
            content = new_content
            sync = false


init = ->
    data = JSON.stringify(
        user_id: user_id
        room: room
    )
    ws.send(HANDSHAKE_SYMBOL + data)


$(document).ready ->
    ws.onmessage = websocket_on_message
    ws.onopen = init

