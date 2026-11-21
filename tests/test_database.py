import os
import tempfile
import threading
import unittest
from datetime import date

from src.database.database import Database, MessageQuery
from src.mail.email_normalizer import NormalizedMessage
from src.utils.dates import local_day_range_ms
from src.utils.text import normalize_text, split_terms


def msg(gid, ms=1_700_000_000_000, **kw):
    kw.setdefault("sender_name", "Fulano")
    kw.setdefault("sender_email", "fulano@exemplo.com")
    kw.setdefault("subject", "Assunto")
    kw.setdefault("body", "Corpo da mensagem")
    return NormalizedMessage(gmail_id=gid, internal_date_ms=ms, **kw)


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "sub", "t.db"))
        self.db.initialize()
        self.acc = self.db.upsert_account("Eu@Gmail.com")

    def tearDown(self):
        self.tmp.cleanup()


class TestSetup(DatabaseTestCase):
    def test_creates_file_and_schema(self):
        self.assertTrue(os.path.exists(self.db.path))
        self.assertEqual(self.db.schema_version(), 1)

    def test_initialize_is_idempotent_and_keeps_data(self):
        self.db.insert_messages(self.acc, [msg("a")])
        self.db.initialize()
        self.assertEqual(self.db.count(), 1)

    def test_newer_schema_is_rejected(self):
        import sqlite3
        conn = sqlite3.connect(self.db.path)
        conn.execute("PRAGMA user_version = 99")
        conn.close()
        with self.assertRaises(RuntimeError):
            self.db.initialize()

    def test_account_email_is_normalized_and_unique(self):
        self.assertEqual(self.db.upsert_account(" eu@gmail.com "), self.acc)
        self.assertEqual(len(self.db.list_accounts()), 1)
        with self.assertRaises(ValueError):
            self.db.upsert_account("  ")


class TestInsertAndDuplicates(DatabaseTestCase):
    def test_duplicates_are_ignored(self):
        self.assertEqual(self.db.insert_messages(self.acc, [msg("a"), msg("b")]), 2)
        self.assertEqual(self.db.insert_messages(self.acc, [msg("a"), msg("c")]), 1)
        self.assertEqual(self.db.count(), 3)

    def test_duplicate_within_same_batch(self):
        self.assertEqual(self.db.insert_messages(self.acc, [msg("a"), msg("a")]), 1)

    def test_same_gmail_id_allowed_in_other_account(self):
        other = self.db.upsert_account("outra@gmail.com")
        self.db.insert_messages(self.acc, [msg("a")])
        self.assertEqual(self.db.insert_messages(other, [msg("a")]), 1)

    def test_missing_gmail_id_rolls_back_batch(self):
        with self.assertRaises(ValueError):
            self.db.insert_messages(self.acc, [msg("ok"), msg("")])
        self.assertEqual(self.db.count(), 0)

    def test_snippet_derived_from_body_and_limits_applied(self):
        self.db.insert_messages(self.acc, [msg("a", body="linha1\n\nlinha2 " + "x" * 500)])
        row = self.db.search()[0]
        self.assertNotIn("\n", row["snippet"])
        self.assertLessEqual(len(row["snippet"]), 200)

    def test_known_gmail_ids(self):
        self.db.insert_messages(self.acc, [msg("a"), msg("b")])
        self.assertEqual(self.db.known_gmail_ids(self.acc, ["a", "z"]), {"a"})
        many = [f"id{i}" for i in range(1500)] + ["b"]
        self.assertEqual(self.db.known_gmail_ids(self.acc, many), {"b"})


class TestUpdates(DatabaseTestCase):
    def test_read_state(self):
        self.db.insert_messages(self.acc, [msg("a", is_read=False)])
        self.assertEqual(self.db.count(MessageQuery(unread_only=True)), 1)
        self.assertTrue(self.db.update_read_state(self.acc, "a", True))
        self.assertEqual(self.db.count(MessageQuery(unread_only=True)), 0)
        self.assertFalse(self.db.update_read_state(self.acc, "nope", True))

    def test_delete_and_categories(self):
        self.db.insert_messages(self.acc, [msg("a"), msg("b"), msg("c")])
        self.assertEqual(self.db.delete_messages(self.acc, ["a", "x"]), 1)
        ids = [m["id"] for m in self.db.search()]
        self.db.update_categories([(ids[0], "Financeiro")])
        self.assertEqual(self.db.count_by_category(), {"Financeiro": 1, "Outros": 1})

    def test_remove_account_cascades(self):
        self.db.insert_messages(self.acc, [msg("a")])
        self.assertEqual(self.db.remove_account("eu@gmail.com"), 1)
        self.assertEqual(self.db.count(), 0)

    def test_clear_messages_resets_sync_state(self):
        self.db.insert_messages(self.acc, [msg("a")])
        self.db.save_sync_state(self.acc, "123")
        self.db.clear_messages()
        self.assertEqual(self.db.count(), 0)
        st = self.db.get_sync_state(self.acc)
        self.assertIsNone(st.history_id)
        self.assertIsNone(st.last_sync_at)
        self.assertEqual(len(self.db.list_accounts()), 1)


class TestSyncState(DatabaseTestCase):
    def test_save_and_reset(self):
        self.assertIsNone(self.db.get_sync_state(self.acc).history_id)
        self.db.save_sync_state(self.acc, "999", 5000)
        st = self.db.get_sync_state(self.acc)
        self.assertEqual((st.history_id, st.last_sync_at), ("999", 5000))
        self.assertEqual(self.db.last_sync_at(), 5000)
        self.db.reset_history(self.acc)
        self.assertIsNone(self.db.get_sync_state(self.acc).history_id)
        self.assertEqual(self.db.get_sync_state(self.acc).last_sync_at, 5000)

    def test_unknown_account(self):
        with self.assertRaises(KeyError):
            self.db.get_sync_state(999)


class TestSearch(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        d = local_day_range_ms
        self.d10 = d(date(2026, 11, 10))[0] + 3_600_000
        self.d12 = d(date(2026, 11, 12))[0] + 3_600_000
        self.db.insert_messages(self.acc, [
            msg("1", self.d10, sender_name="Banco Itaú", sender_email="no-reply@itau.com.br",
                subject="Sua FATURA está disponível", body="Boleto vence dia 15", category="Financeiro"),
            msg("2", self.d12, sender_name="Prof. José", sender_email="jose@faculdade.edu",
                subject="Atividade da disciplina", body="Entrega 100% online, prova_final", category="Acadêmico",
                is_read=False),
            msg("3", self.d12 + 1000, sender_name="Loja", sender_email="loja@shop.com",
                subject="Pedido enviado", body="Rastreamento", category="Compras"),
        ])

    def subjects(self, **kw):
        return [m["subject"] for m in self.db.search(MessageQuery(**kw))]

    def test_ordering_newest_first(self):
        self.assertEqual([m["gmail_id"] for m in self.db.search()], ["3", "2", "1"])

    def test_accent_and_case_insensitive(self):
        self.assertEqual(self.subjects(text="itau"), ["Sua FATURA está disponível"])
        self.assertEqual(self.subjects(text="ITAÚ"), ["Sua FATURA está disponível"])
        self.assertEqual(self.subjects(text="fatura esta"), ["Sua FATURA está disponível"])
        self.assertEqual(self.subjects(text="jose"), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(text="ACADEMICO"), [])  # categoria não faz parte do texto

    def test_all_terms_must_match(self):
        self.assertEqual(self.subjects(text="boleto fatura"), ["Sua FATURA está disponível"])
        self.assertEqual(self.subjects(text="boleto rastreamento"), [])

    def test_like_wildcards_are_literal(self):
        self.assertEqual(self.subjects(text="100%"), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(text="prova_final"), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(text="prova%final"), [])
        self.assertEqual(self.subjects(text="_"), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(text="\\"), [])

    def test_sender_and_subject_filters(self):
        self.assertEqual(self.subjects(sender="itau.com"), ["Sua FATURA está disponível"])
        self.assertEqual(self.subjects(sender="jose faculdade"), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(subject="pedido"), ["Pedido enviado"])
        self.assertEqual(self.subjects(subject="boleto"), [])  # só no corpo

    def test_category_unread_and_combination(self):
        self.assertEqual(self.subjects(category="Compras"), ["Pedido enviado"])
        self.assertEqual(self.subjects(unread_only=True), ["Atividade da disciplina"])
        self.assertEqual(self.subjects(category="Compras", text="fatura"), [])

    def test_date_range_is_half_open(self):
        lo, hi = local_day_range_ms(date(2026, 11, 12))
        self.assertEqual(len(self.db.search(MessageQuery(date_from_ms=lo, date_to_ms=hi))), 2)
        lo, hi = local_day_range_ms(date(2026, 11, 10))
        self.assertEqual(self.subjects(date_from_ms=lo, date_to_ms=hi), ["Sua FATURA está disponível"])
        lo, hi = local_day_range_ms(date(2026, 11, 11))
        self.assertEqual(self.subjects(date_from_ms=lo, date_to_ms=hi), [])

    def test_pagination_and_counts(self):
        self.assertEqual(len(self.db.search(limit=2)), 2)
        self.assertEqual([m["gmail_id"] for m in self.db.search(limit=2, offset=2)], ["1"])
        self.assertEqual(self.db.count(), 3)
        self.assertEqual(self.db.count(MessageQuery(category="Financeiro")), 1)
        self.assertEqual(self.db.count_by_category(),
                         {"Financeiro": 1, "Acadêmico": 1, "Compras": 1})
        self.assertEqual(self.db.count_by_category(account_id=999), {})

    def test_get_message_has_body_and_list_does_not(self):
        first = self.db.search()[0]
        self.assertNotIn("body", first)
        full = self.db.get_message(first["id"])
        self.assertEqual(full["body"], "Rastreamento")
        self.assertIs(full["is_read"], True)
        self.assertIsNone(self.db.get_message(99999))

    def test_sql_injection_attempt_is_inert(self):
        self.assertEqual(self.subjects(text="'; DROP TABLE messages; --"), [])
        self.assertEqual(self.db.count(), 3)

    def test_iter_for_classification_batches(self):
        batches = list(self.db.iter_for_classification(batch_size=2))
        self.assertEqual([len(b) for b in batches], [2, 1])
        self.assertIn("body", batches[0][0])

    def test_uses_indexes(self):
        import sqlite3
        conn = sqlite3.connect(self.db.path)
        plan = " ".join(r[3] for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM messages WHERE category = ? "
            "ORDER BY internal_date DESC LIMIT 10", ("Compras",)))
        conn.close()
        self.assertIn("idx_messages_category_date", plan)


class TestConcurrency(DatabaseTestCase):
    def test_reader_while_writer_thread_runs(self):
        errors = []

        def writer():
            try:
                for i in range(20):
                    self.db.insert_messages(self.acc, [msg(f"w{i}-{j}") for j in range(25)])
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        t = threading.Thread(target=writer)
        t.start()
        while t.is_alive():
            self.db.count()
            self.db.search(limit=10)
        t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.db.count(), 500)


class TestTextUtils(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_text("  Fatura  do   CARTÃO\n"), "fatura do cartao")
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(split_terms("Ação  Rápida"), ["acao", "rapida"])


if __name__ == "__main__":
    unittest.main()
