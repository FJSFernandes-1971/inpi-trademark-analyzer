#!/usr/bin/env python3
"""Trademark conflict risk screener for intellectual property law firms."""

from __future__ import annotations  # must be the first non-comment/code statement

import csv
import datetime as dt
import pathlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Tuple

from inpi_fetch import fetch_inpi_by_class

DATASET_PATH = pathlib.Path("marcas.csv")

ACTIVE_STATUSES = {
    "active",
    "registered",
    "granted",
    "vigente",
    "deferida",
    "deferido",
    "em vigor",
    "registro de marca em vigor",
}

# -----------------------------
# Data models
# -----------------------------


@dataclass
class TrademarkRecord:
    name: str
    nice_class: str
    status: str
    numero: str = ""
    titular: str = ""


@dataclass
class MatchResult:
    record: TrademarkRecord
    text_similarity: float
    phonetic_match: bool
    same_class: bool
    score: int


# -----------------------------
# Normalization + similarity
# -----------------------------


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def soundex(value: str) -> str:
    """Basic Soundex implementation suitable for quick screening."""
    value = "".join(ch for ch in normalize_text(value) if ch.isalpha())
    if not value:
        return "0000"

    mappings = {
        **dict.fromkeys(list("bfpv"), "1"),
        **dict.fromkeys(list("cgjkqsxz"), "2"),
        **dict.fromkeys(list("dt"), "3"),
        "l": "4",
        **dict.fromkeys(list("mn"), "5"),
        "r": "6",
    }

    first_letter = value[0].upper()
    encoded = []
    previous_code = mappings.get(value[0], "")

    for char in value[1:]:
        code = mappings.get(char, "")
        if code and code != previous_code:
            encoded.append(code)
        previous_code = code

    return (first_letter + "".join(encoded) + "000")[:4]


def similarity_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


# -----------------------------
# CSV fallback loader
# -----------------------------


def read_records(path: pathlib.Path) -> list[TrademarkRecord]:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset '{path.name}' was not found. Create it with columns: "
            "existing trademark name, class, status."
        )

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("The dataset is empty or missing headers.")

        lower_headers = {h.strip().lower(): h for h in reader.fieldnames if h}

        def resolve_header(options: Iterable[str]) -> str | None:
            for option in options:
                if option in lower_headers:
                    return lower_headers[option]
            return None

        name_col = resolve_header(
            [
                "existing trademark name",
                "trademark name",
                "name",
                "marca",
                "nome",
            ]
        )
        class_col = resolve_header(["class", "nice class", "classe", "ncl"])
        status_col = resolve_header(["status", "situation", "situacao", "situação"])

        # Optional columns
        numero_col = resolve_header(["numero", "número", "processo"])
        titular_col = resolve_header(["titular", "requerente"])

        if not all([name_col, class_col, status_col]):
            raise ValueError(
                "Dataset headers must include columns for trademark name, class, and status."
            )

        records: list[TrademarkRecord] = []
        for row in reader:
            name = (row.get(name_col) or "").strip()
            nice_class = (row.get(class_col) or "").strip()
            status = (row.get(status_col) or "").strip()
            numero = (row.get(numero_col) or "").strip() if numero_col else ""
            titular = (row.get(titular_col) or "").strip() if titular_col else ""
            if name:
                records.append(
                    TrademarkRecord(
                        name=name,
                        nice_class=nice_class,
                        status=status,
                        numero=numero,
                        titular=titular,
                    )
                )

    if not records:
        raise ValueError("Dataset contains no valid trademark records.")

    return records


# -----------------------------
# INPI loader (primary)
# -----------------------------


def load_records_from_inpi(trademark_name: str, nice_class: str) -> list[TrademarkRecord]:
    """
    Fetches public records from INPI (PEPI) using the working Playwright scraper.
    Returns [] on any error so caller can fallback to CSV.
    """
    try:
        inpi = fetch_inpi_by_class(marca=trademark_name, ncl=str(nice_class), headless=True)
    except Exception as e:
        print("INPI ERROR:", repr(e))
        return []

    if not inpi:
        return []

    all_records: list[TrademarkRecord] = []
    seen: set[tuple[str, str, str]] = set()

    for r in inpi:
        name = (getattr(r, "marca", "") or "").strip()
        cls = (getattr(r, "classe", "") or str(nice_class)).strip()
        status = (getattr(r, "situacao", "") or "N/D").strip()
        numero = (getattr(r, "numero", "") or "").strip()
        titular = (getattr(r, "titular", "") or "").strip()

        key = (normalize_text(name), normalize_text(cls), normalize_text(status))
        if name and key not in seen:
            seen.add(key)
            all_records.append(
                TrademarkRecord(
                    name=name,
                    nice_class=cls,
                    status=status,
                    numero=numero,
                    titular=titular,
                )
            )

    return all_records


def load_records(trademark_name: str, nice_class: str) -> Tuple[list[TrademarkRecord], str]:
    inpi_records = load_records_from_inpi(trademark_name, nice_class)
    if inpi_records:
        return inpi_records, "INPI"
    return read_records(DATASET_PATH), "CSV"


# -----------------------------
# Scoring + classification
# -----------------------------


def extract_ncl(value: str) -> str:
    """
    Normaliza classe para comparação.
    Exemplos:
      - "30" -> "30"
      - "NCL(8) 30" -> "30"
      - "33 : 10" -> "10" (pega o último número disponível)
    """
    v = normalize_text(value)
    parts = [p for p in v.replace(":", " ").split() if p.isdigit()]
    return parts[-1] if parts else v


def calculate_match(candidate_name: str, candidate_class: str, record: TrademarkRecord) -> MatchResult:
    text_similarity = similarity_ratio(candidate_name, record.name)
    phonetic_match = soundex(candidate_name) == soundex(record.name)

    cand_ncl = extract_ncl(candidate_class)
    rec_ncl = extract_ncl(record.nice_class)
    same_class = cand_ncl == rec_ncl

    status_norm = normalize_text(record.status)
    active_status = any(s in status_norm for s in ACTIVE_STATUSES)

    score = 0
    if text_similarity >= 0.90:
        score += 55
    elif text_similarity >= 0.80:
        score += 40
    elif text_similarity >= 0.70:
        score += 25
    elif text_similarity >= 0.60:
        score += 12

    if phonetic_match:
        score += 25
    if same_class:
        score += 25
    if active_status:
        score += 15

    return MatchResult(
        record=record,
        text_similarity=text_similarity,
        phonetic_match=phonetic_match,
        same_class=same_class,
        score=min(score, 100),
    )


def classify_risk(score: int) -> str:
    if score >= 75:
        return "HIGH RISK"
    if score >= 45:
        return "MEDIUM RISK"
    return "LOW RISK"


def format_reason(match: MatchResult) -> str:
    reasons: list[str] = []
    if match.text_similarity >= 0.80:
        reasons.append("high textual proximity")
    elif match.text_similarity >= 0.65:
        reasons.append("moderate textual proximity")

    if match.phonetic_match:
        reasons.append("phonetic overlap under Soundex")
    if match.same_class:
        reasons.append("identical Nice class")

    # aqui usamos "contains" porque status do INPI pode vir longo
    status_norm = normalize_text(match.record.status)
    if any(s in status_norm for s in ACTIVE_STATUSES):
        reasons.append("prior mark appears active/registered")

    return "; ".join(reasons) if reasons else "limited overlap indicators"


# -----------------------------
# Reporting + Opinion
# -----------------------------


def generate_recommendations(risk_level: str) -> list[str]:
    base = [
        "Run an expanded INPI search using radicals, spelling variants, singular/plural and compound expressions.",
        "Assess conceptual proximity (meaning/idea) and phonetic variants beyond basic Soundex where relevant.",
        "Confirm status and scope of cited records (class specification, goods/services description, owner and distinctiveness).",
        "If relevant conflicts appear, consider mitigation: composite mark, figurative element, specification refinement, or alternative naming.",
    ]
    if risk_level == "HIGH RISK":
        base.insert(0, "Consider immediate naming alternatives before protocol to reduce refusal and opposition exposure.")
    elif risk_level == "MEDIUM RISK":
        base.insert(0, "Proceed with caution: validate coexistence feasibility and strengthen distinctiveness elements.")
    else:
        base.insert(0, "Low conflict indicators: still validate with expanded search before final registrability opinion.")
    return base


def generate_report(
    trademark_name: str,
    nice_class: str,
    business_segment: str,
    matches: list[MatchResult],
    source_label: str,
) -> str:
    top_matches = sorted(matches, key=lambda item: item.score, reverse=True)[:5]
    highest_score = top_matches[0].score if top_matches else 0
    risk_level = classify_risk(highest_score)

    date_str = dt.datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [
        "BUSCA DE ANTERIORIDADE – TRIAGEM PRELIMINAR (USO INTERNO)",
        f"Date: {date_str}",
        "",
        "I. Candidate Mark Information",
        f"- Proposed trademark: {trademark_name}",
        f"- Nice class: {nice_class}",
        f"- Business segment: {business_segment}",
        "",
        "II. Data Source",
        f"- Records source: {source_label}",
        "",
        "III. Methodological Review",
        "This preliminary screening reviewed prior records with emphasis on:",
        "(a) textual similarity (SequenceMatcher),",
        "(b) phonetic proximity (Soundex), and",
        "(c) class-based conflict priority (same Nice class).",
        "",
        "IV. Risk Determination",
        f"Result: {risk_level}",
    ]

    if top_matches:
        lines.append("Grounds (top indications):")
        for idx, match in enumerate(top_matches, start=1):
            extra = []
            if match.record.numero:
                extra.append(f"Process/No.: {match.record.numero}")
            if match.record.titular:
                extra.append(f"Owner: {match.record.titular}")
            extra_txt = (" | " + " ; ".join(extra)) if extra else ""

            lines.extend(
                [
                    f"{idx}. Prior mark: {match.record.name}",
                    f"   - Class/Status: {match.record.nice_class} / {match.record.status}{extra_txt}",
                    f"   - Similarity index: {match.text_similarity * 100:.1f}%",
                    f"   - Conflict rationale: {format_reason(match)}.",
                    f"   - Weighted conflict score: {match.score}/100",
                ]
            )
    else:
        lines.append("Grounds: no prior records available for comparative assessment.")

    lines.extend(["", "V. Recommendations (next steps)"])
    for rec in generate_recommendations(risk_level):
        lines.append(f"- {rec}")

    lines.extend(
        [
            "",
            "VI. Professional Note",
            "This report is a screening aid for internal legal triage and does not replace",
            "a full registrability opinion, including jurisdiction-specific case law review,",
            "market coexistence evidence, examiner practice, and goods/services specification analysis.",
        ]
    )

    return "\n".join(lines)


def generate_legal_opinion(
    trademark_name: str,
    nice_class: str,
    segment: str,
    risk: str,
    matches: list[MatchResult],
) -> str:
    # pega até 3 conflitos mais fortes para citar no parecer
    top = sorted(matches, key=lambda m: m.score, reverse=True)[:3]
    refs = []
    for m in top:
        ref = f"{m.record.name}"
        if m.record.numero:
            ref += f" (proc. {m.record.numero})"
        if m.record.titular:
            ref += f", titular {m.record.titular}"
        refs.append(ref)

    refs_txt = "; ".join(refs) if refs else "anterioridades relevantes"

    if risk == "HIGH RISK":
        fundamento = (
            f"identificou-se colidência relevante com {refs_txt}, incluindo sinais idênticos ou praticamente idênticos "
            f"na mesma classe, o que eleva substancialmente o risco de indeferimento e/ou oposição. "
            "Em tese, trata-se de cenário compatível com risco de confusão/associação pelo consumidor médio, "
            "à luz da vedação legal do art. 124, XIX, da LPI."
        )
        orientacao = (
            "Recomenda-se não protocolar a marca nominativa isolada. "
            "Como mitigação, sugere-se: (i) criação de marca composta com elemento distintivo forte; "
            "(ii) alteração fonética/ortográfica substancial; (iii) eventual reposicionamento de sinal e especificação "
            "mais precisa de produtos/serviços; e (iv) nova rodada de buscas (radicais, variações e compostas) antes de decidir o depósito."
        )
    elif risk == "MEDIUM RISK":
        fundamento = (
            f"foram encontradas anterioridades potencialmente conflitantes ({refs_txt}), com semelhança fonética e/ou textual "
            "na mesma classe ou em classes próximas, o que pode gerar exigência ou oposição dependendo do entendimento do INPI."
        )
        orientacao = (
            "O depósito pode ser considerado, porém com cautela. "
            "Recomenda-se reforçar distintividade (marca mista/figurativa), ajustar a especificação e realizar busca ampliada "
            "por variações fonéticas, grafias e marcas compostas antes da decisão final."
        )
    else:
        fundamento = (
            "não foram identificadas anterioridades fortes com potencial claro de confusão direta ao consumidor médio, "
            "mantendo-se, contudo, a recomendação de busca ampliada e validação de especificação."
        )
        orientacao = (
            "Em princípio, o depósito mostra-se viável, sujeito à revisão final e a eventuais oposições de terceiros."
        )

    date_str = dt.datetime.now().strftime("%Y-%m-%d")
    return f"""PARECER PRELIMINAR DE REGISTRABILIDADE (MINUTA)

Data: {date_str}

Marca pretendida: {trademark_name}
Classe (Nice/NCL): {nice_class}
Segmento: {segment}

Síntese:
Com base na busca de anterioridade realizada, conclui-se que {fundamento}

Orientação:
{orientacao}

Observação:
Minuta automática para apoio interno e revisão do advogado responsável. Não substitui parecer completo,
incluindo análise de especificação, estratégia de depósito, coexistência e prática examinadora.
"""


# -----------------------------
# CLI
# -----------------------------


def main() -> None:
    print("Trademark Preliminary Risk Analyzer")
    trademark_name = input("Enter trademark name: ").strip()
    nice_class = input("Enter Nice class: ").strip()
    business_segment = input("Enter business segment: ").strip()

    if not trademark_name or not nice_class or not business_segment:
        raise ValueError("All inputs are required: trademark name, Nice class, business segment.")

    records, source = load_records(trademark_name, nice_class)

    matches = [calculate_match(trademark_name, nice_class, record) for record in records]
    report = generate_report(trademark_name, nice_class, business_segment, matches, source)

    highest = max((m.score for m in matches), default=0)
    risk_level = classify_risk(highest)
    opinion = generate_legal_opinion(trademark_name, nice_class, business_segment, risk_level, matches)

    print("\n" + report)
    print("\n" + opinion)


if __name__ == "__main__":
    main()
