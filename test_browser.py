from playwright.sync_api import sync_playwright

URL = "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # abre janela pra você ver
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    print("TITLE:", page.title())
    page.wait_for_timeout(5000)  # 5s pra você ver a página
    browser.close()
