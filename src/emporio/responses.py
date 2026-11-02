"""Polimento limitado: preserva fatos e remove ofertas sem ferramenta de execução.

Não é um detector geral de idioma nem uma garantia de qualidade semântica.
"""

import re

from .policies import normalize

CLOSING = "Posso ajudar com mais informações sobre instrumentos ou políticas da loja?"
CAPABILITIES = (
    "Este chat consulta informações e orienta. Agendamentos, compras e alterações "
    "precisam ser tratados pela equipe da loja."
)
ACTION = r"(?:agend\w*|(?:marcar|marcasse|marque)\b|reserv\w*|registr\w*|cancel\w*|reembols\w*|encaminh\w*|finaliz\w*\s+(?:a\s+|uma\s+|sua\s+)?compra|realiz\w*\s+(?:a\s+|uma\s+|sua\s+)?compra)"
OFFER = re.compile(
    r"\b(?:(?:gostaria|deseja|quer)\s+(?:de\s+)?(?:que\s+eu\s+)?"
    r"|(?:posso|podemos|vamos|vou|irei)\s+(?:(?:te|lhe|ajudar|a|ja|agora)\s+){0,4})" + ACTION
)
CLAIM = re.compile(r"\b(?:agendei|marquei|reservei|registrei|cancelei|reembolsei|encaminhei)\b")
ENGLISH_CLOSING = re.compile(r"^(?:would you like|can i help|is there anything else|let me know|thank you)\b")


def non_negated_match(pattern: re.Pattern, text: str) -> bool:
    for match in pattern.finditer(text):
        prefix = text[:match.start()]
        if not re.search(r"\b(?:nao|nunca)\s+(?:\w+\s+){0,3}$", prefix):
            return True
    return False


def polish_response(text: str) -> str:
    # Correção pontual observada na avaliação; não altera termos técnicos de produtos.
    text = re.sub(r"\balgo\s+else\b", "mais alguma coisa", text, flags=re.I)
    removed_offer = removed_claim = False
    paragraphs = []
    for paragraph in text.split("\n"):
        kept = []
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", paragraph):
            normalized = normalize(sentence.strip())
            if non_negated_match(CLAIM, normalized):
                removed_claim = True
            elif non_negated_match(OFFER, normalized) or ENGLISH_CLOSING.search(normalized):
                removed_offer = True
            else:
                kept.append(sentence)
        paragraphs.append(" ".join(kept))
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(paragraphs)).strip()
    if removed_claim:
        result = (result + "\n\n" + CAPABILITIES).strip()
    elif removed_offer:
        if not result:
            return CAPABILITIES + " " + CLOSING
        if not result.endswith("?"):
            result += "\n\n" + CLOSING
    return result
