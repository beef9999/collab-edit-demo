editor = ace.edit("collab_editor")
editor.setTheme("ace/theme/monokai")
editor.setPrintMarginColumn(120)
editor.$blockScrolling = Infinity
editor.getSession().setMode("ace/mode/python")


content = ''
user_id = $("#user_id").text()
room = $("#room").text()
cursor = null
ws = new WebSocket('wss://collabedit.pood.xyz/api/websocket')
dmp = new diff_match_patch
user_registed = false


apply_patch = (patch, str) ->
    x = dmp.patch_apply(patch, str)
    return x[0]


generate_patch = (str1, str2) ->
    diff = dmp.diff_main(str1, str2)
    patch = dmp.patch_make(str1, diff)
    return patch


update_patch = (patch, succ_callback) ->
    if patch != null
        patch = dmp.patch_toText(patch)
    data = JSON.stringify(
        uid: user_id
        patch: patch
        room: room
    )
    update_succ = (resp, textStatus, jqXHR) ->
        patch_str = JSON.parse(resp)
        patch = dmp.patch_fromText(patch_str)
        succ_callback(patch)

    update_fail = (jqXHR, textStatus, errorThrown) ->
        console.error("Server error: #{textStatus}")

    $.ajax '/api/update',
        type: 'POST'
        data: data
        error: update_fail
        success: update_succ


update_patch_succ_callback = (patch) ->
    content = apply_patch(patch, "")
    editor.setValue(content)
    editor.navigateTo(0, 0)
    window.setInterval(loop_forever, 2000)


loop_forever = ->
    editor.setReadOnly(true)
    editor.getSession()
    sel = editor.getSelection()
    is_empty = sel.isEmpty()
    if not is_empty
        editor.setReadOnly(false)
        return

    new_content = editor.getValue()
    cursor = editor.getCursorPosition()
    patch = generate_patch(content, new_content)
    patch_str = dmp.patch_toText(patch)
    data = JSON.stringify(
        uid: user_id
        patch: patch_str
        room: room
    )
    ws.send(data)


websocket_on_message = (evt) ->
    resp = evt.data
    if not user_registed
        if resp.startsWith('----handshake----\n')
            resp_data = JSON.parse(resp.split('\n')[1])
            resp_user_id = resp_data['user_id']
            resp_room = resp_data['room']
            if resp_user_id == user_id and resp_room == room
                user_registed = true
                update_patch(null, update_patch_succ_callback)
            else
                window.alert('Server error')
    else
        patch_str = JSON.parse(resp)
        patch = dmp.patch_fromText(patch_str)
        content = apply_patch(patch, content)
        editor.setValue(content)
        editor.navigateTo(cursor.row, cursor.column)
        editor.setReadOnly(false)


init = ->
    data = JSON.stringify(
        user_id: user_id
        room: room
    )
    ws.send('----handshake----\n' + data)


$(document).ready ->
    ws.onmessage = websocket_on_message
    ws.onopen = init

