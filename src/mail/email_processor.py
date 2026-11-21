"""Pipeline pós-coleta: resposta da Gmail API -> normaliza -> classifica."""
from src.classifier.email_classifier import classify
from src.mail.email_normalizer import NormalizedMessage, normalize_message


def process_message(raw: dict) -> NormalizedMessage:
    msg = normalize_message(raw)
    msg.category = classify(msg.sender_name, msg.sender_email, msg.subject, msg.body)
    return msg
