import unittest

from asitop.asitop import build_parser, clip_text, resolve_terminal_kind, sanitize_terminal_kind


class AsitopTests(unittest.TestCase):
    def test_clip_text_truncates_with_ascii_ellipsis(self):
        self.assertEqual(clip_text("abcdef", 5), "ab...")

    def test_clip_text_respects_short_widths(self):
        self.assertEqual(clip_text("abcdef", 3), "abc")

    def test_show_cores_flag_is_false_by_default(self):
        args = build_parser().parse_args([])
        self.assertFalse(args.show_cores)

    def test_show_cores_flag_enables_core_mode(self):
        args = build_parser().parse_args(["--show_cores"])
        self.assertTrue(args.show_cores)

    def test_sanitize_terminal_kind_fixes_ghostty_typo(self):
        self.assertEqual(sanitize_terminal_kind("xterm-ghossty"), "xterm-ghostty")

    def test_resolve_terminal_kind_falls_back_to_xterm_256color(self):
        attempted = []

        def fake_setupterm(kind, _fd):
            attempted.append(kind)
            if kind == "xterm-ghostty":
                raise RuntimeError("missing terminfo")

        resolved = resolve_terminal_kind("xterm-ghossty", setupterm=fake_setupterm)

        self.assertEqual(resolved, "xterm-256color")
        self.assertEqual(attempted[:2], ["xterm-ghostty", "xterm-256color"])


if __name__ == "__main__":
    unittest.main()
