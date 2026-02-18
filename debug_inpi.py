from playwright.sync_api import sync_playwright

URL = "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # 1) PASSAR PELO PORTÃO: pesquisa anônima
    # Tenta vários textos possíveis porque o INPI muda rótulos.
    for txt in [
        "Pesquisar anonimamente",
        "Pesquisa anônima",
        "Acessar anonimamente",
        "Continuar sem login",
        "Continuar como visitante",
        "Continuar",
    ]:
        try:
            page.get_by_text(txt, exact=False).click(timeout=2500)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            break
        except Exception:
            pass

    # Às vezes ele redireciona para home e precisa voltar ao formulário:
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # 2) preencher e pesquisar
    page.locator('input[name="marca"]').fill("solano")
    page.locator('input[name="ncl"]').fill("30")

    clicked = False
    for label in ["Pesquisar", "Buscar", "Consultar"]:
        try:
            page.get_by_role("button", name=label).click(timeout=2500)
            clicked = True
            break
        except Exception:
            pass
    if not clicked:
        try:
            page.locator('input[type="submit"]').first.click(timeout=2500)
            clicked = True
        except Exception:
            pass

    page.wait_for_timeout(6000)

    # salva evidências
    page.screenshot(path="inpi_result.png", full_page=True)
    html = page.content()
    with open("inpi_result.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ Salvei inpi_result.png e inpi_result.html na pasta do projeto.")
    input("Deixei a janela aberta. Quando quiser fechar, aperte ENTER aqui no terminal...")

    browser.close()
