from playwright.sync_api import sync_playwright

HOME = "https://busca.inpi.gov.br/pePI/"
SEARCH = "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp"

def snap(page, name):
    page.screenshot(path=name, full_page=True)
    print("📸", name, "| URL:", page.url)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
    snap(page, "01_home.png")

    # Tenta clicar no botão "Continuar" (vários jeitos)
    clicked = False

    # 1) role button
    try:
        page.get_by_role("button", name="Continuar", exact=False).click(timeout=3000)
        clicked = True
    except Exception:
        pass

    # 2) input submit/button com value
    if not clicked:
        for sel in [
            'input[type="submit"][value*="Continuar"]',
            'input[type="button"][value*="Continuar"]',
            'button:has-text("Continuar")',
            'text=Continuar',
        ]:
            try:
                page.locator(sel).first.click(timeout=3000)
                clicked = True
                break
            except Exception:
                pass

    # 3) tentar dentro de iframes
    if not clicked:
        for frame in page.frames:
            try:
                frame.locator('input[value*="Continuar"], button:has-text("Continuar"), text=Continuar').first.click(timeout=3000)
                clicked = True
                break
            except Exception:
                pass

    page.wait_for_timeout(2000)
    snap(page, "02_after_continue.png")

    # Agora tenta ir pra página de pesquisa
    page.goto(SEARCH, wait_until="domcontentloaded", timeout=60000)
    snap(page, "03_search.png")

    input("Se chegou na busca, aperte ENTER para fechar…")
    browser.close()

