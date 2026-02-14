from mcp.server.fastmcp import FastMCP
from pathlib import Path

mcp = FastMCP("filesystem-mcp")

# pasta onde a IA pode agir
BASE_DIR = Path(r"C:\codex_data")

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

@mcp.tool()
def escrever_arquivo(nome: str, conteudo: str) -> str:
    """Cria ou sobrescreve um arquivo de texto."""
    arquivo = (BASE_DIR / nome).resolve()
    if not str(arquivo).startswith(str(BASE_DIR)):
        raise ValueError("Acesso não autorizado")

    arquivo.write_text(conteudo, encoding="utf-8")
    return f"Arquivo {nome} salvo com sucesso."

if __name__ == "__main__":
    mcp.run()