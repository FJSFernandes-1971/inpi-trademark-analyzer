from mcp.server.fastmcp import FastMCP
from pathlib import Path

mcp = FastMCP("filesystem-mcp")

# Pasta permitida (segurança): seus Documentos
BASE_DIR = Path.home() / "Documentos"

@mcp.tool()
def listar_arquivos() -> list[str]:
    """Lista arquivos na pasta permitida."""
    return [p.name for p in BASE_DIR.iterdir() if p.is_file()]

@mcp.tool()
def ler_arquivo(nome: str) -> str:
    """Lê um arquivo de texto da pasta permitida."""
    arquivo = (BASE_DIR / nome).resolve()
    if not str(arquivo).startswith(str(BASE_DIR)):
        raise ValueError("Acesso não autorizado")

    return arquivo.read_text(encoding="utf-8")
