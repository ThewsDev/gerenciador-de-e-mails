import os
import tempfile
import unittest
from datetime import datetime

from src.database.database import Database
from src.ui.formatting import format_list_date, format_size, to_view_model


def ms(*args):
    return int(datetime(*args).timestamp() * 1000)


class TestFormatting(unittest.TestCase):
    now = datetime(2026, 11, 17, 15, 0)

    def test_list_dates(self):
        self.assertEqual(format_list_date(ms(2026, 11, 17, 9, 42), self.now), "09:42")
        self.assertEqual(format_list_date(ms(2026, 11, 16, 23, 59), self.now), "Ontem")
        self.assertEqual(format_list_date(ms(2026, 11, 14, 8, 0), self.now), "Sábado")
        self.assertEqual(format_list_date(ms(2026, 11, 10, 8, 0), self.now), "10/11/2026")
        self.assertEqual(format_list_date(ms(2025, 1, 2, 8, 0), self.now), "02/01/2025")

    def test_size(self):
        self.assertEqual(format_size(10), "10 B")
        self.assertEqual(format_size(2048), "2 KB")
        self.assertEqual(format_size(3 * 1024 * 1024), "3.0 MB")

    def test_view_model_fallbacks(self):
        row = {"sender_name": "", "sender_email": "a@b.com", "subject": "", "snippet": "x",
               "internal_date": ms(2026, 11, 17, 1, 0)}
        view = to_view_model(row, self.now)
        self.assertEqual((view["sender"], view["subject"], view["preview"]),
                         ("a@b.com", "(Sem assunto)", "x"))
        row["sender_email"] = ""
        self.assertEqual(to_view_model(row, self.now)["sender"], "(Remetente desconhecido)")


if __name__ == "__main__":
    unittest.main()
