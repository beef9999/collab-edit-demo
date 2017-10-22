import diff_match_patch_py3

dmp = diff_match_patch_py3.diff_match_patch()


def apply_patch(patch, string):
    x = dmp.patch_apply(patch, string)
    return x[0]


def generate_patch(string1, string2):
    diff = dmp.diff_main(string1, string2)
    patch = dmp.patch_make(string1, diff)
    return patch


patch = dmp.patch_fromText("")
print(patch)