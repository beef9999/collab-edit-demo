content = ''
user_id = ''
ws = new WebSocket('wss://43.241.216.214/websocket')
dmp = new diff_match_patch


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
    )
    update_succ = (resp, textStatus, jqXHR) ->
        patch_str = JSON.parse(resp)
        patch = dmp.patch_fromText(patch_str)
        succ_callback(patch)

    update_fail = (jqXHR, textStatus, errorThrown) ->
        console.error("Server error: #{textStatus}")

    $.ajax '/update',
        type: 'POST'
        data: data
        error: update_fail
        success: update_succ


update_patch_succ_callback = (patch) ->
    content = apply_patch(patch, "")
    $("#text1").val(content)
    window.setInterval(loop_forever, 500)


loop_forever = ->
    $("#text1").attr("readonly", true)
    text1 = $("#text1").val()
    patch = generate_patch(content, text1)
    patch_str = dmp.patch_toText(patch)
    data = JSON.stringify(
        uid: user_id
        patch: patch_str
    )
    ws.send(data)


websocket_on_message = (evt) ->
    resp = evt.data
    patch_str = JSON.parse(resp)
    patch = dmp.patch_fromText(patch_str)
    content = apply_patch(patch, content)
    $("#text1").val(content)
    $("#text1").attr("readonly", false)


init = ->
    user_id = UUID.generate()
    update_patch(null, update_patch_succ_callback)


$(document).ready ->
    ws.onmessage = websocket_on_message
    ws.onopen = init



