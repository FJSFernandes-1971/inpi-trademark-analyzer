from __future__ import annotations

from dataclasses import dataclass
from typing import List
from playwright.sync_api import sync_playwright

HOME = "https://busca.inpi.gov.br/pePI/"
SEARCH = "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp"


@dataclass
class INPIRecord:
    marca: str
    classe: str
    situacao: str
    numero: str = ""
    titular: str = ""


def fetch_inpi_by_class(marca: str, ncl: str, headless: bool = True) -> List[INPIRecord]:
    registros: List[INPIRecord] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        # 1) entrar no portal
        page.goto(HOME, timeout=60000)

        # 2) tentar "Continuar" (pesquisa anônima)
        try:
            page.get_by_role("button", name="Continuar").click(timeout=5000)
        except Exception:
            pass

        # 3) ir para pesquisa por classe básica
        page.goto(SEARCH, timeout=60000)

        # 4) esperar campos existirem
        page.wait_for_selector("input[type=text]", timeout=20000)
        inputs = page.locator("input[type=text]")

        # normalmente: 0 = marca / 1 = ncl
        inputs.nth(0).fill(marca)
        inputs.nth(1).fill(str(ncl))

        # 5) clicar pesquisar
        page.locator("input[type=submit]").first.click()

        # 6) esperar resultados aparecerem
        page.wait_for_selector("text=RESULTADO DA PESQUISA", timeout=20000)

        # 7) localizar linhas: cada resultado tem um link com MarcasServletController (número do processo)
        rows = page.locator("a[href*='MarcasServletController']")
        count = rows.count()

        # 8) pegar headers (th) da tabela de resultados, pra mapear por nome
        #    (fazemos uma vez, pegando a primeira linha)
        headers: List[str] = []
        try:
            if count > 0:
                first_tr = rows.nth(0).locator("xpath=ancestor::tr")
                table = first_tr.locator("xpath=ancestor::table[1]")
                ths = table.locator("tr th")
                headers = [ths.nth(j).inner_text().strip().lower() for j in range(ths.count())]
        except Exception:
            headers = []

        def row_pick(row_dict: dict, *names: str) -> str:
            # tenta match exato ou parcial no nome da coluna
            for name in names:
                name = name.lower()
                for k, v in row_dict.items():
                    if k == name or name in k:
                        return (v or "").strip()
            return ""

        for i in range(count):
            try:
                tr = rows.nth(i).locator("xpath=ancestor::tr")
                tds = tr.locator("td")
                values = [tds.nth(j).inner_text().strip() for j in range(tds.count())]
               


                row = {}
                for j, val in enumerate(values):
                    key = headers[j] if j < len(headers) and headers[j] else f"col_{j}"
                    row[key] = val

                # 1) tenta mapear por header (quando existir)
                numero = row_pick(row, "número", "numero", "processo")
                marca_nome = row_pick(row, "marca", "sinal", "nome")
                situacao = row_pick(row, "situação", "situacao", "status")
                classe = row_pick(row, "classe", "ncl")
                titular = row_pick(row, "titular", "requerente")

                # 2) fallback por posição (INPI frequentemente não expõe <th> confiável)
                # Layout observado:
                # [0]=numero, [3]=marca, [5]=situacao, [6]=titular, [7]=classe
                if not numero and len(values) > 0:
                 numero = values[0].strip()
                if not marca_nome and len(values) > 3:
                    marca_nome = values[3].strip()
                if not situacao and len(values) > 5:
                    situacao = values[5].strip()
                if not titular and len(values) > 6:
                    titular = values[6].strip()
                if not classe and len(values) > 7:
                    classe = values[7].strip()

                # 3) último fallback: acha a marca digitada em qualquer coluna
                if not marca_nome:
                    for v in values:
                        if v.strip().upper() == marca.strip().upper():
                            marca_nome = v.strip()
                            break


                registros.append(
                    INPIRecord(
                        marca=marca_nome,
                        classe=classe,
                        situacao=situacao,
                        numero=numero,
                        titular=titular,
                    )
                )

            except Exception as e:
                print("erro lendo linha:", e)
                continue

        browser.close()

    return registros
