from __future__ import annotations

from pathlib import Path
from typing import List

from mcp.server.fastmcp import FastMCP
from pypdf import PdfReader

mcp = FastMCP("filesystem-mcp")

# Pastas-raiz permitidas (segurança): qualquer pasta abaixo dessas raízes
ALLOWED_ROOTS = [
    Path("C:/"),
    Path("D:/"),
]

# Pasta ativa inicial (mude com definir_diretorio)
ACTIVE_DIR = Path("C:/codex_data").resolve()


def _clean_input(s: str) -> str:
    """Limpa aspas e espaços típicos de copiar/colar no Windows."""
    return (s or "").strip().strip('"').strip("'")


def _is_under_allowed_roots(p: Path) -> bool:
    """Verifica se p está dentro de alguma raiz permitida."""
    p = p.resolve()
    for root in ALLOWED_ROOTS:
        root = root.resolve()
        try:
            p.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _safe_path(p: Path) -> Path:
    """Valida se o caminho está dentro das raízes permitidas."""
    p = p.resolve()
    if not _is_under_allowed_roots(p):
        raise ValueError("Acesso não autorizado (fora das raízes permitidas)")
    return p


def _safe_file(nome: str) -> Path:
    """Monta e valida um arquivo dentro do diretório ativo."""
    global ACTIVE_DIR

    nome = _clean_input(nome)
    if not nome:
        raise ValueError("Nome de arquivo vazio")

    # monta caminho relativo à pasta ativa
    arquivo = (ACTIVE_DIR / nome).resolve()

    # 1) precisa estar em C:/ ou D:/
    arquivo = _safe_path(arquivo)

    # 2) precisa estar dentro do ACTIVE_DIR (evita ..\..)
    base = ACTIVE_DIR.resolve()
    try:
        arquivo.relative_to(base)
    except ValueError:
        raise ValueError("Acesso não autorizado (fora do diretório ativo)")

    return arquivo


@mcp.tool()
def definir_diretorio(caminho: str) -> str:
    """Define a pasta ativa onde as tools vão operar."""
    global ACTIVE_DIR

    caminho = _clean_input(caminho)
    novo = Path(caminho).resolve()

    if not novo.exists():
        return "Caminho não existe"
    if not novo.is_dir():
        return "Não é uma pasta"
    if not _is_under_allowed_roots(novo):
        return "Diretório não permitido (fora de C:/ ou D:/)"

    ACTIVE_DIR = novo
    return f"Pasta ativa: {ACTIVE_DIR}"


@mcp.tool()
def listar_pastas() -> List[str]:
    """Lista subpastas do diretório ativo."""
    return [p.name for p in ACTIVE_DIR.iterdir() if p.is_dir()]


@mcp.tool()
def listar_arquivos() -> List[str]:
    """Lista arquivos do diretório ativo."""
    return [p.name for p in ACTIVE_DIR.iterdir() if p.is_file()]


@mcp.tool()
def escrever_arquivo(nome: str, conteudo: str) -> str:
    """Cria ou sobrescreve um arquivo de texto dentro do diretório ativo."""
    nome = _clean_input(nome)
    _safe_file(nome).write_text(conteudo or "", encoding="utf-8")
    return f"{nome} salvo"


@mcp.tool()
def ler_arquivo(nome: str) -> str:
    """
    Lê arquivo de texto dentro do diretório ativo.
    Tenta UTF-8 / Windows (cp1252) / Latin-1 / UTF-16 e escolhe o melhor.
    Se parecer PDF/DOCX/Imagem, manda usar tool específica.
    """
    nome = _clean_input(nome)
    arquivo = _safe_file(nome)

    if arquivo.is_dir():
        raise ValueError("Isso é uma pasta, não um arquivo.")

    # Se for claramente um tipo binário, já barra
    if arquivo.suffix.lower() in {".pdf", ".docx", ".png", ".jpg", ".jpeg"}:
        raise ValueError(
            f"'{arquivo.name}' não é texto puro (parece {arquivo.suffix}). "
            "Use extrair_texto_pdf para PDF."
        )

    data = arquivo.read_bytes()
    nul_count = data.count(b"\x00")

    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"]

    best_text = None
    best_bad = 10**18

    for enc in encodings:
        try:
            text = data.decode(enc, errors="replace")
        except Exception:
            continue

        bad = text.count("\ufffd")
        bad += text.count("\x00") * 10

        if bad < best_bad:
            best_bad = bad
            best_text = text

    if best_text is None:
        raise ValueError("Não consegui decodificar este arquivo como texto.")

    # Heurística binário (muitos nulos e muito quebrado)
    if nul_count > 0 and best_bad > 50:
        raise ValueError(
            f"'{arquivo.name}' parece binário/estruturado. "
            "Para PDF/DOCX, precisamos de extração."
        )

    return best_text


@mcp.tool()
def extrair_texto_pdf(nome: str, max_paginas: int = 0) -> str:
    """
    Extrai texto de um PDF dentro do diretório ativo.
    max_paginas:
      - 0 = todas as páginas
      - N = só as primeiras N páginas (útil pra teste)
    """
    nome = _clean_input(nome)
    arquivo = _safe_file(nome)

    if arquivo.suffix.lower() != ".pdf":
        raise ValueError("Este tool é só para arquivos .pdf")

    reader = PdfReader(str(arquivo))
    total = len(reader.pages)

    if max_paginas and max_paginas > 0:
        total = min(total, max_paginas)

    partes: List[str] = []
    for i in range(total):
        txt = reader.pages[i].extract_text() or ""
        txt = txt.replace("\x00", "").strip()
        partes.append(f"\n--- PÁGINA {i+1} ---\n{txt}")

    texto_final = "\n".join(partes).strip()
    if not texto_final:
        return (
            "Não consegui extrair texto desse PDF. "
            "Ele pode ser escaneado (imagem) — aí precisa OCR."
        )
    return texto_final


@mcp.tool()
def dossie_processo(
    nome_saida: str = "DOSSIÊ.txt",
    max_paginas_por_pdf: int = 0,
    incluir_arquivos_txt: bool = True
) -> str:
    """
    Gera um dossiê consolidado no diretório ativo (ACTIVE_DIR).
    - nome_saida: nome do arquivo de saída (.txt)
    - max_paginas_por_pdf: 0 = todas as páginas; N = só as primeiras N páginas de cada PDF
    - incluir_arquivos_txt: se True, também inclui .txt/.md
    """
    nome_saida = _clean_input(nome_saida)
    saida = _safe_file(nome_saida)

    linhas: List[str] = []
    linhas.append(f"DOSSIÊ DO DIRETÓRIO: {ACTIVE_DIR}")
    linhas.append("=" * 80)

    arquivos = sorted([p for p in ACTIVE_DIR.iterdir() if p.is_file()], key=lambda x: x.name.lower())

    processados = 0
    pulados = 0

    for arq in arquivos:
        ext = arq.suffix.lower()

        # evita incluir o próprio dossiê
        if arq.resolve() == saida.resolve():
            continue

        # PDFs
        if ext == ".pdf":
            linhas.append("\n\n" + "#" * 80)
            linhas.append(f"ARQUIVO: {arq.name}")
            linhas.append("#" * 80)

            try:
                reader = PdfReader(str(arq))
                total = len(reader.pages)

                if max_paginas_por_pdf and max_paginas_por_pdf > 0:
                    total = min(total, max_paginas_por_pdf)

                texto_pdf: List[str] = []
                for i in range(total):
                    txt = reader.pages[i].extract_text() or ""
                    txt = txt.replace("\x00", "").strip()
                    if txt:
                        texto_pdf.append(f"\n--- PÁGINA {i+1} ---\n{txt}")

                if texto_pdf:
                    linhas.append("\n".join(texto_pdf))
                else:
                    linhas.append(
                        "⚠️ Não consegui extrair texto deste PDF. "
                        "Ele pode ser escaneado (imagem)."
                    )

                processados += 1

            except Exception as e:
                linhas.append(f"❌ Erro ao ler PDF: {e}")
                pulados += 1

            continue

        # TXT/MD (opcional)
        if incluir_arquivos_txt and ext in {".txt", ".md"}:
            linhas.append("\n\n" + "#" * 80)
            linhas.append(f"ARQUIVO: {arq.name}")
            linhas.append("#" * 80)

            try:
                try:
                    conteudo = arq.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    conteudo = arq.read_text(encoding="cp1252", errors="replace")

                linhas.append(conteudo.strip())
                processados += 1

            except Exception as e:
                linhas.append(f"❌ Erro ao ler TXT/MD: {e}")
                pulados += 1

            continue

        pulados += 1

    texto_final = "\n".join(linhas).strip()
    saida.write_text(texto_final, encoding="utf-8")

    return (
        f"Dossiê gerado com sucesso: {saida.name}\n"
        f"Processados: {processados}\n"
        f"Pulados: {pulados}\n"
        f"Diretório: {ACTIVE_DIR}"
    )


if __name__ == "__main__":
    mcp.run()