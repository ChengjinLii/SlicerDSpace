from __future__ import annotations

import unittest

from shared.ui_output_loading import qbytearray_to_text


class FakeByteArray:
    def __init__(self, value):
        self._value = value

    def data(self):
        return self._value


class UiOutputLoadingTest(unittest.TestCase):
    def test_decodes_common_byte_values(self) -> None:
        self.assertEqual(qbytearray_to_text(None), "")
        self.assertEqual(qbytearray_to_text("hello"), "hello")
        self.assertEqual(qbytearray_to_text(b"hello"), "hello")
        self.assertEqual(qbytearray_to_text(bytearray(b"hello")), "hello")

    def test_decodes_qbytearray_like_data(self) -> None:
        self.assertEqual(qbytearray_to_text(FakeByteArray(b"hello")), "hello")
        self.assertEqual(qbytearray_to_text(FakeByteArray(bytearray(b"hello"))), "hello")
        self.assertEqual(qbytearray_to_text(FakeByteArray("hello")), "hello")

    def test_invalid_object_returns_empty_string(self) -> None:
        self.assertEqual(qbytearray_to_text(object()), "")


if __name__ == "__main__":
    unittest.main()
