import base64
import os
import tempfile
import unittest

from src.classifier.email_classifier import classify
from src.database.database import Database, MessageQuery
from src.mail.email_processor import process_message
from src.mail.gmail_api import AuthError, GmailClient, HistoryExpired
from src.services.sync_service import SyncService


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def raw_message(mid, sender, subject, body, labels=("INBOX", "UNREAD"), html=False):
    mime = "text/html" if html else "text/plain"
    return {"id": mid, "threadId": "t" + mid, "internalDate": "1760000000000",
            "labelIds": list(labels), "snippet": body[:50],
            "payload": {"mimeType": "multipart/alternative", "headers": [
                {"name": "From", "value": sender}, {"name": "Subject", "value": subject}],
                "parts": [{"mimeType": mime, "body": {"data": b64(body)}}]}}


class FakeResponse:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data or {}, headers or {}

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kw):
        self.calls.append((url, kw.get("params")))
        return self.responses.pop(0)


class ClassifierTests(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(classify("Banco", "a@banco.com", "Sua fatura está disponível"), "Financeiro")
        self.assertEqual(classify("Loja", "p@loja.com", "Pedido enviado", "rastreamento"), "Compras")
        self.assertEqual(classify("Prof", "p@faculdade.edu", "Prova de Engenharia"), "Acadêmico")
        self.assertEqual(classify("X", "x@y.com", "Reunião do projeto"), "Trabalho")
        self.assertEqual(classify("News", "n@x.com", "Promoção com 50% de desconto"), "Marketing")
        self.assertEqual(classify("Ana", "ana@x.com", "Oi, tudo bem?"), "Outros")


class NormalizerTests(unittest.TestCase):
    def test_plain_and_html(self):
        msg = process_message(raw_message("1", '"Nora Loren" <nora@x.com>', "Olá", "corpo simples"))
        self.assertEqual((msg.sender_name, msg.sender_email), ("Nora Loren", "nora@x.com"))
        self.assertEqual(msg.body, "corpo simples")
        self.assertFalse(msg.is_read)
        html = process_message(raw_message("2", "a@b.com", "x", "<style>p{}</style><p>Olá <b>mundo</b></p>",
                                           labels=("INBOX",), html=True))
        self.assertEqual(html.body, "Olá mundo")
        self.assertTrue(html.is_read)

    def test_encoded_subject(self):
        msg = process_message(raw_message("3", "a@b.com", "=?UTF-8?B?Q2Fyw6Fjb3Jlcw==?=", "x"))
        self.assertEqual(msg.subject, "Carácores")


class ApiTests(unittest.TestCase):
    def test_401_is_auth_error(self):
        client = GmailClient("t", FakeSession(FakeResponse(401)))
        with self.assertRaises(AuthError):
            client.get_profile()

    def test_history_404_is_expired(self):
        client = GmailClient("t", FakeSession(FakeResponse(404)))
        with self.assertRaises(HistoryExpired):
            client.list_history("1")

    def test_pagination(self):
        session = FakeSession(
            FakeResponse(200, {"messages": [{"id": "a"}], "nextPageToken": "n"}),
            FakeResponse(200, {"messages": [{"id": "b"}]}))
        self.assertEqual(GmailClient("t", session).list_inbox_ids(10), ["a", "b"])
        self.assertEqual(session.calls[1][1]["pageToken"], "n")


class FakeClient:
    def __init__(self):
        self.messages = {"m1": raw_message("m1", "Banco <b@banco.com>", "Fatura", "boleto"),
                         "m2": raw_message("m2", "Ana <a@x.com>", "Oi", "tudo bem")}
        self.history, self.expired, self.fetched = [], False, []

    def get_profile(self):
        return {"emailAddress": "Me@Gmail.com", "historyId": "100"}

    def list_inbox_ids(self, limit):
        return list(self.messages)

    def get_message(self, mid):
        self.fetched.append(mid)
        return self.messages[mid]

    def list_history(self, start):
        if self.expired:
            raise HistoryExpired()
        return self.history, "200"


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.dir.name, "t.db"))
        self.db.initialize()
        self.client = FakeClient()

    def tearDown(self):
        self.dir.cleanup()

    def run_sync(self):
        return SyncService(self.db, self.client).run()

    def test_full_then_incremental(self):
        r = self.run_sync()
        self.assertTrue(r.full)
        self.assertEqual(r.added, 2)
        self.assertEqual(self.db.count_by_category()["Financeiro"], 1)
        aid = self.db.get_account_id("me@gmail.com")
        self.assertEqual(self.db.get_sync_state(aid).history_id, "100")

        self.client.messages["m3"] = raw_message("m3", "L <l@loja.com>", "Pedido enviado", "frete")
        self.client.history = [
            {"messagesAdded": [{"message": {"id": "m3"}}, {"message": {"id": "m1"}}]},
            {"messagesDeleted": [{"message": {"id": "m2"}}]},
            {"labelsRemoved": [{"message": {"id": "m1"}, "labelIds": ["UNREAD"]}]}]
        self.client.fetched.clear()
        r = self.run_sync()
        self.assertFalse(r.full)
        self.assertEqual((r.added, r.deleted), (1, 1))
        self.assertEqual(self.client.fetched, ["m3"])          # m1 já conhecido: não rebaixa
        self.assertEqual(self.db.count(), 2)
        self.assertEqual(self.db.count(MessageQuery(unread_only=True)), 1)  # só m3
        self.assertEqual(self.db.get_sync_state(aid).history_id, "200")

    def test_expired_history_triggers_full_sync(self):
        self.run_sync()
        self.client.expired = True
        r = self.run_sync()
        self.assertTrue(r.full)
        self.assertEqual(self.db.count(), 2)  # sem duplicatas


if __name__ == "__main__":
    unittest.main()

