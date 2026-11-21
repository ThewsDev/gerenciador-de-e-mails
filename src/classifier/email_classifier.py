"""Classificação local por palavras-chave (sem IA, sem rede).

Para incluir uma categoria ou palavra, edite RULES (e a cor em settings.CATEGORY_COLORS).
Os textos são comparados sem acento e sem caixa, por palavra inteira/prefixo.
"""
import re

from src.config import settings
from src.utils.text import normalize_text

# Peso de cada campo: um assunto que casa vale mais que uma menção no corpo.
WEIGHTS = {"subject": 3, "sender": 2, "body": 1}
BODY_CHARS = 2000

# Palavras sem acento/minúsculas. Terminar com '*' aceita sufixos (ex.: 'pagament*').
RULES = {
    "Acadêmico": ["faculdade", "universidade", "disciplina", "professor*", "aula*", "prova*",
                  "tcc", "monografia", "matricula", "semestre", "bolsa", "coordenacao",
                  "campus", "academic*", "moodle", "edu"],
    "Trabalho": ["reuniao", "projeto*", "cliente*", "contrato", "vaga",
                 "entrevista", "curriculo", "linkedin", "meeting", "sprint", "deadline",
                 "relatorio", "equipe", "slack", "jira", "github"],
    "Financeiro": ["fatura", "boleto", "pix", "extrato", "cartao", "pagamento*", "saldo",
                   "banco", "transferencia", "imposto*", "cobranca", "emprestimo", "invoice",
                   "nubank", "itau", "bradesco", "santander", "paypal", "vencimento"],
    "Compras": ["pedido*", "compra*", "entrega", "rastreamento", "rastreio", "nota fiscal",
                "frete", "carrinho", "amazon", "mercado livre", "shopee", "aliexpress",
                "order", "shipped", "recibo"],
    "Marketing": ["promocao", "promocoes", "oferta*", "desconto*", "cupom", "newsletter",
                  "descadastrar", "cancelar inscricao", "unsubscribe", "black friday",
                  "imperdivel", "gratis", "novidades", "sale"],
}


def _compile(rules):
    compiled = {}
    for category, words in rules.items():
        parts = []
        for word in words:
            word = normalize_text(word)
            prefix = word.endswith("*")
            parts.append(re.escape(word.rstrip("*")) + ("" if prefix else r"\b"))
        compiled[category] = re.compile(r"\b(?:" + "|".join(parts) + ")") if parts else None
    return compiled


_PATTERNS = _compile(RULES)


def classify(sender_name: str = "", sender_email: str = "", subject: str = "",
             body: str = "") -> str:
    """Categoria de maior pontuação; empate vai para a primeira da lista; sem pontos = Outros."""
    fields = {
        "subject": normalize_text(subject),
        "sender": normalize_text(f"{sender_name} {sender_email}"),
        "body": normalize_text((body or "")[:BODY_CHARS]),
    }
    best, best_score = settings.DEFAULT_CATEGORY, 0
    for category, pattern in _PATTERNS.items():
        if pattern is None:
            continue
        score = sum(weight * len(pattern.findall(fields[field]))
                    for field, weight in WEIGHTS.items())
        if score > best_score:
            best, best_score = category, score
    return best
