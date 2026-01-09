from prreviewbot.core.diff_hunks import parse_unified_diff_hunks, validate_line_range_against_patch


def test_parse_unified_diff_hunks_and_validate():
    patch = """@@ -10,2 +20,5 @@
-old
+new1
+new2
+new3
 context
"""
    hunks = parse_unified_diff_hunks(patch)
    assert len(hunks) == 1
    assert hunks[0].new_start == 20
    assert hunks[0].new_len == 5

    # within range ok
    s, e, side = validate_line_range_against_patch(patch=patch, start_line=21, end_line=23, side="new")
    assert (s, e, side) == (21, 23, "new")

    # outside range -> nulled
    s2, e2, side2 = validate_line_range_against_patch(patch=patch, start_line=1, end_line=2, side="new")
    assert (s2, e2, side2) == (None, None, None)


