from pathlib import Path

PASTA = Path(".")  # pasta atual

def analisar_pasta(pasta):
    arquivos = list(pasta.iterdir())

    categorias = {
        "peticoes": [],
        "decisoes": [],
        "provas": [],
        "outros": []
    }

    for arq in arquivos:
        nome = arq.name.lower()

        if any(p in nome for p in ["peticao", "inicial", "contestacao"]):
            categorias["peticoes"].append(arq.name)

        elif any(p in nome for p in ["decisao", "sentenca", "acordao"]):
            categorias["decisoes"].append(arq.name)

        elif any(p in nome for p in ["doc", "anexo", "comprovante"]):
            categorias["provas"].append(arq.name)

        else:
            categorias["outros"].append(arq.name)

    return categorias


def gerar_relatorio(categorias):
    linhas = ["RESUMO DO PROCESSO\n"]

    for tipo, lista in categorias.items():
        linhas.append(f"\n--- {tipo.upper()} ---")
        for item in lista:
            linhas.append(item)

    Path("indice_processo.txt").write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    cat = analisar_pasta(PASTA)
    gerar_relatorio(cat)
    print("Indice criado!")