"""Base de conhecimento das políticas da loja (RAG leve, sem embeddings).

O manual de políticas (data/politicas_da_loja.md) tem apenas ~8
páginas e muda raramente — não é o tipo de corpus que justifica um
banco vetorial. Em vez disso:

1. Um RESUMO curto e estático (hora de funcionamento, endereço, regra
   de escopo, tom de voz) vai sempre no system prompt — são fatos
   usados em quase toda conversa e são baratos de manter sempre
   presentes (ver prompts.py).
2. O restante do manual (trocas/devoluções, parcelamento, frete,
   garantia, LGPD etc.) fica disponível por meio de uma ferramenta,
   `consultar_politicas`, que faz *retrieval lexical* (contagem de
   palavras em comum, ponderada por raridade — uma versão simplificada
   de TF-IDF) sobre as seções do documento e devolve as mais
   relevantes, na íntegra.

Por que lexical e não embeddings: é determinístico, não tem custo de
API nem de infraestrutura extra (nenhuma dependência além da
biblioteca padrão do Python) e, para ~10 seções de texto, é tão eficaz
quanto um vetor de embeddings — o gargalo de precisão de um RAG
pequeno como esse não é o algoritmo de busca, é o tamanho do corpus.
Se o manual crescesse para dezenas de documentos ou mudasse com
frequência, essa seria a primeira peça a trocar por um índice vetorial
(ex.: Chroma/FAISS) — a ferramenta exposta ao modelo (`consultar_politicas`)
não mudaria de assinatura, só a implementação por trás dela.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from . import config

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-zà-ú0-9]+", re.IGNORECASE)

# palavras comuns em português que não ajudam a diferenciar seções.
# Já escritas sem acento, porque o filtro de stopwords roda DEPOIS da
# normalização de acentos em _tokenize (ver abaixo) — "é" vira "e"
# antes de chegar aqui.
_STOPWORDS = {
    "a", "o", "os", "as", "de", "do", "da", "dos", "das", "em", "um", "uma",
    "e", "ou", "para", "com", "por", "no", "na", "nos", "nas", "que", "se",
    "ao", "aos", "as", "sobre", "como", "pelo", "pela", "ser", "ate",
    "eu", "meu", "minha", "voce", "voces",
}

# Comprimento do prefixo usado como "stem" (raiz) de cada palavra — uma
# alternativa deliberadamente simples a um stemmer de português de
# verdade (ex.: o algoritmo RSLP do NLTK), que exigiria uma dependência
# extra só para isso. Comparar só os 5 primeiros caracteres já resolve
# os pares que importam neste manual: "arrependi" e "arrependimento"
# -> "arrep"; "devolver" e "devolução" -> "devol"; "parcelar" e
# "parcelamento" -> "parce". Não é linguisticamente rigoroso (vai
# juntar palavras que não deveriam, ocasionalmente), mas numa busca
# lexical sobre ~10 seções curtas, o ganho de recall compensa muito
# o ruído — ver tests/test_policy.py para o caso que motivou isso.
_STEM_LEN = 5


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _stem(word: str) -> str:
    return word[:_STEM_LEN] if len(word) > _STEM_LEN else word


@dataclass(frozen=True)
class PolicySection:
    heading: str
    level: int
    text: str  # inclui o próprio cabeçalho, pronto para ser citado


def _tokenize(text: str) -> list[str]:
    folded = _strip_accents(text.lower())
    words = [w for w in _WORD_RE.findall(folded) if w not in _STOPWORDS]
    return [_stem(w) for w in words]


@lru_cache(maxsize=1)
def load_full_policy_text() -> str:
    """Retorna o manual de políticas inteiro, como Markdown."""

    return config.POLICY_MD.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_policy_sections() -> tuple[PolicySection, ...]:
    """Quebra o manual em seções de nível 2 (##) e 3 (###).

    Cada seção de nível 3 fica aninhada dentro do texto da seção de
    nível 2 que a contém, mas também é indexada separadamente, para
    que uma pergunta bem específica (ex.: "direito de arrependimento")
    encontre a subseção exata em vez de só a seção ampla ("Trocas e
    Devoluções").
    """

    text = load_full_policy_text()
    matches = list(_HEADING_RE.finditer(text))
    sections: list[PolicySection] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if heading.startswith(("Empório da Música", "Nota de qualidade")):
            continue  # título do documento / nota interna, não é conteúdo de política
        sections.append(PolicySection(heading=heading, level=level, text=body))
    return tuple(sections)


def _section_score(query_terms: list[str], section_terms: list[str], idf: dict[str, float]) -> float:
    if not section_terms:
        return 0.0
    section_counts: dict[str, int] = {}
    for t in section_terms:
        section_counts[t] = section_counts.get(t, 0) + 1
    score = 0.0
    for term in query_terms:
        if term in section_counts:
            # TF (normalizada pelo tamanho da seção) * IDF
            tf = section_counts[term] / len(section_terms)
            score += tf * idf.get(term, 0.0)
    return score


def retrieve_relevant_sections(query: str, top_k: int = 2) -> list[PolicySection]:
    """Retorna as `top_k` seções do manual mais relevantes para `query`.

    Implementação enxerga o manual todo para calcular IDF (quão rara é
    cada palavra entre as seções) e pontua cada seção pela soma de
    TF*IDF dos termos da pergunta que aparecem nela — a mesma ideia de
    TF-IDF clássico, só que calculada à mão para não precisar de
    scikit-learn/numpy como dependência.
    """

    sections = load_policy_sections()
    query_terms = _tokenize(query)
    if not query_terms or not sections:
        return []

    section_term_lists = [_tokenize(s.text) for s in sections]

    doc_count = len(sections)
    idf: dict[str, float] = {}
    for term in set(query_terms):
        containing = sum(1 for terms in section_term_lists if term in terms)
        # +1 no denominador e no numerador (smoothing) evita divisão por
        # zero e evita que um termo ausente de todas as seções exploda o score
        idf[term] = math.log((1 + doc_count) / (1 + containing)) + 1.0

    scored = [
        (_section_score(query_terms, terms, idf), section)
        for section, terms in zip(sections, section_term_lists)
    ]
    scored = [(score, section) for score, section in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [section for _, section in scored[:top_k]]
