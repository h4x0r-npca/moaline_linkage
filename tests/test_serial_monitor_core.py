import os
import tempfile
import unittest
from datetime import datetime

from serial_monitor_core import (
    ReceiptLogWriter,
    ReceiptSplitter,
    default_config,
    parse_hex_patterns,
    preview_text,
)


class ReceiptSplitterTests(unittest.TestCase):
    def test_cut_command_finishes_receipt(self):
        splitter = ReceiptSplitter(
            cut_patterns=parse_hex_patterns("1D 56 01"),
            idle_timeout_ms=999999,
            min_bytes=1,
        )

        receipts = splitter.feed(b"\x1b@hello\x1d\x56\x01")

        self.assertEqual(receipts, [b"\x1b@hello\x1d\x56\x01"])
        self.assertEqual(splitter.flush_all(), [])

    def test_split_multiple_receipts_from_one_chunk(self):
        splitter = ReceiptSplitter(
            cut_patterns=parse_hex_patterns("1D 56 01"),
            idle_timeout_ms=999999,
            min_bytes=1,
        )

        receipts = splitter.feed(b"A\x1d\x56\x01B\x1d\x56\x01")

        self.assertEqual(receipts, [b"A\x1d\x56\x01", b"B\x1d\x56\x01"])

    def test_idle_timeout_is_fallback(self):
        now = [0.0]
        splitter = ReceiptSplitter(
            cut_patterns=parse_hex_patterns("1D 56 01"),
            idle_timeout_ms=1000,
            min_bytes=3,
            clock=lambda: now[0],
        )

        self.assertEqual(splitter.feed(b"ABC"), [])
        now[0] = 1.1

        self.assertEqual(splitter.flush_idle(), [b"ABC"])


class ReceiptLogWriterTests(unittest.TestCase):
    def test_writes_same_binary_data_to_both_dirs(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            writer = ReceiptLogWriter([first, second])
            data = b"\x1b@\xc0\xfc\xba\xcf\x1d\x56\x01"

            paths = writer.write("COM10", data, datetime(2026, 5, 30, 21, 5, 30))

            self.assertEqual(
                [os.path.basename(path) for path in paths],
                ["COM10_20260530210530.LOG", "COM10_20260530210530.LOG"],
            )
            for path in paths:
                with open(path, "rb") as fp:
                    self.assertEqual(fp.read(), data)

    def test_preview_keeps_korean_text_without_control_bytes(self):
        text = preview_text(b"\x1b@\xc0\xfc\xba\xcf\xb3\xb2\xbf\xf8\x00\r\n", "cp949")

        self.assertIn("전북남원", text)
        self.assertNotIn("\x1b", text)


class MonitorConfigTests(unittest.TestCase):
    def test_default_config_does_not_select_ports(self):
        config = default_config(["COM1", "COM2"])

        self.assertEqual(config.selected_ports, [])
        self.assertFalse(config.direct_monitor_enabled)
        self.assertIn("COM1", config.port_settings)
        self.assertIn("COM2", config.port_settings)


if __name__ == "__main__":
    unittest.main()
