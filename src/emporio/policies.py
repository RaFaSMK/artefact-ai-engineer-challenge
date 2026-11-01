"""Extração por seção e recuperação textual, com fonte e exceções preservadas."""

import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

# Estrutura do manual recebido. Mudanças no PDF devem passar pela validação de ingestão.
HEADINGS = [
    ("1", "Sobre a loja", r"1\.\s*Sobre"),
    ("1.1", "Missão", r"1\.1\s+Missão"),
    ("1.2", "Dados da empresa", r"1\.2\s+Dados"),
    ("2", "Horário de funcionamento", r"2\.\s*Horário"),
    ("3", "Formas de pagamento", r"3\.\s*Formas"),
    ("3.1", "Regras de parcelamento", r"3\.1\s+Regras"),
    ("4", "Trocas e devoluções", r"4\.\s*Política"),
    ("4.1", "Arrependimento em compras online", r"4\.1\s+Direito"),
    ("4.2", "Trocas por defeito", r"4\.2\s+Trocas"),
    ("4.3", "Trocas por preferência", r"4\.3\s+Trocas"),
    ("4.4", "Itens não elegíveis para troca", r"4\.4\s+Itens"),
    ("5", "Frete e entregas", r"5\.\s*Política"),
    ("5.1", "Entregas na região de Campo Grande", r"5\.1\s+Entregas"),
    ("5.2", "Entregas para outras cidades", r"5\.2\s+Entregas"),
    ("5.3", "Código de rastreamento", r"5\.3\s+Código"),
    ("6", "Promoções e descontos", r"6\.\s*Promoções"),
    ("6.1", "Tipos de promoção", r"6\.1\s+Tipos"),
    ("6.2", "Regras de promoções", r"6\.2\s+Regras"),
    ("7", "Atendimento via WhatsApp", r"7\.\s*Atendimento"),
    ("7.1", "Diretrizes de atendimento", r"7\.1\s+Diretrizes"),
    ("7.2", "Fluxo de atendimento", r"7\.2\s+Fluxo"),
    ("7.3", "Situações especiais", r"7\.3\s+Situações"),
    ("8", "Garantia", r"8\.\s*Garantia"),
    ("8.1", "Garantia legal descrita no manual", r"8\.1\s+Garantia"),
    ("8.2", "Garantia do fabricante", r"8\.2\s+Garantia"),
    ("8.3", "Exclusões de garantia", r"8\.3\s+O\s+que"),
    ("9", "Privacidade e proteção de dados", r"9\.\s*Privacidade"),
    ("10", "Disposições finais", r"10\.\s*Disposições"),
]

NOTES = {
    "1.2": "O manual diverge sobre WhatsApp (seção 7) e e-mail (capa com domínio sem acento). Não tratar contato como confirmado.",
    "3": "A seção 3.1 detalha valores diferentes da tabela geral. Usar o detalhamento para 4–12x e apontar a interpretação.",
    "3.1": "Até 3x há uma ressalva ambígua de R$ 50. Confirmar casos dessa faixa. Para 4–6x: parcela mínima R$ 80; 7–12x: R$ 100. É interpretação da seção específica.",
    "4.1": "Orientação do manual, sem aprovação automática. Perguntar canal de compra, data efetiva de recebimento e condição do produto. Não há data efetiva de recebimento nos pedidos.",
    "4.2": "Troca comercial por defeito e garantia são situações distintas; consultar também a seção 8. Não emitir parecer jurídico.",
    "5.1": "Exatamente R$ 500 não está coberto pelas faixas descritas: confirmar com a loja. Não inferir região metropolitana apenas por cidade sem cadastro de cobertura.",
    "5.2": "Não há integração de cotação nem peso/dimensões suficientes. Não inventar valor de frete.",
    "6.2": "PIX não acumula com promoção. is_active é o indicador do snapshot; a base não contém datas de validade.",
    "7": "Há outro telefone na seção 1.2. Priorizar esta seção para WhatsApp é uma hipótese documentada, e o contato precisa de confirmação.",
}


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(c))


def extract_sections(pdf_path: Path) -> list[dict]:
    pages = []
    for page in PdfReader(pdf_path).pages:
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        text = re.sub(r"Empório da Música Manual de Políticas e Procedimentos", "", text)
        text = re.sub(r"Página\s+\d+", "", text)
        pages.append(text)
    full = "\n".join(pages)
    offsets = []
    offset = 0
    for page in pages:
        offsets.append(offset)
        offset += len(page) + 1
    matches = []
    for section, title, pattern in HEADINGS:
        match = re.search(pattern, full)
        if not match:
            raise ValueError(f"Seção {section} não encontrada no PDF; revisar extração.")
        matches.append((match.start(), section, title))
    matches.sort()
    result = []
    for i, (start, section, title) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(full)
        body = full[start:end].strip()
        first = max(j for j, off in enumerate(offsets) if off <= start) + 1
        last_position = start + len(full[start:end].rstrip()) - 1
        last = max(j for j, off in enumerate(offsets) if off <= last_position) + 1
        result.append({"section": section, "title": title, "body": body,
                       "page_start": first, "page_end": last,
                       "note": NOTES.get(section, "")})
    return result


def preferred_sections(query: str) -> list[str]:
    """Complementos de domínio preservam regras e ambiguidades do manual pequeno."""
    q = normalize(query)
    rules = [
        (("whatsapp", "telefone", "contato", "email", "e-mail"), ["7", "1.2"]),
        (("parcel", "juros", "credito", "cartao"), ["3.1", "3"]),
        (("pix", "cumul", "promoc", "desconto"), ["6.2", "3"]),
        (("devol", "arrepend", "devolver"), ["4.1", "4.4"]),
        (("defeito",), ["4.2", "8.1", "8.3"]),
        (("garantia",), ["8.1", "8.2", "8.3"]),
        (("troca", "trocar"), ["4.3", "4.4", "4.1"]),
        (("frete", "entrega", "sedex", "jadlog", "pac"), ["5.1", "5.2"]),
        (("rastre",), ["5.3"]),
        (("horario", "abre", "aberto", "fecha", "funciona", "sabado", "domingo", "feriado"), ["2"]),
        (("endereco", "localiz", "onde fica"), ["1.2"]),
        (("acessorio", "pedal", "cabo", "palheta", "amplificador", "case"), ["1", "7.1"]),
        (("privacidade", "dados pessoais", "lgpd"), ["9"]),
    ]
    selected = []
    for keywords, sections in rules:
        if any(word in q for word in keywords):
            selected.extend(sections)
    return list(dict.fromkeys(selected))[:3]


def search_terms(query: str) -> list[str]:
    stop = {"como", "qual", "quais", "para", "uma", "com", "que", "por", "posso",
            "meu", "minha", "tem", "voces", "loja", "sobre", "dos", "das", "pode"}
    return [w for w in re.findall(r"[a-z0-9]+", normalize(query))
            if len(w) >= 3 and w not in stop][:16]


def required_clarification(query: str, result: dict) -> str | None:
    """Uma lacuna conhecida do manual não pode virar condição comercial criada pelo LLM."""
    q = normalize(query)
    is_exact = any(word in q for word in ("exatamente", "exato", "igual a"))
    is_shipping = "frete" in q or "entrega" in q
    is_500 = bool(re.search(r"\b500(?:[.,]00)?\b", q))
    retrieved = any(c.get("section") == "5.1" and c.get("note") for c in result.get("chunks", []))
    if is_exact and is_shipping and is_500 and retrieved:
        return ("Para uma compra de exatamente R$ 500,00, o manual deixa a condição do frete local em aberto. "
                "Precisamos confirmar com a equipe da loja: com os dados fornecidos, não posso garantir "
                "a gratuidade nem definir uma cobrança para esse valor.")
    return None
