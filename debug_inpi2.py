from playwright.sync_api import sync_playwright

START = "https://busca.inpi.gov.br/pePI/"

def snap(page, name):
    page.screenshot(path=name, full_page=True)
    print(f"📸 screenshot: {name} | URL: {page.url}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print("Abrindo INPI…")
    page.goto(START, wait_until="domcontentloaded", timeout=60000)
    snap(page, "01_home.png")

    # Tenta achar o caminho "anônimo" por vários jeitos: botão, link, texto parcial
    candidates = [
        ("role=link name~anon", lambda: page.get_by_role("link", name="anon", exact=False).click(timeout=2000)),
        ("role=button name~anon", lambda: page.get_by_role("button", name="anon", exact=False).click(timeout=2000)),
        ("text~anonimamente", lambda: page.get_by_text("anon", exact=False).click(timeout=2000)),
        ("text~sem login", lambda: page.get_by_text("sem login", exact=False).click(timeout=2000)),
        ("text~visitante", lambda: page.get_by_text("visitante", exact=False).click(timeout=2000)),
        ("text~continuar", lambda: page.get_by_text("continuar", exact=False).click(timeout=2000)),
    ]

    clicked = False
    for label, action in candidates:
        try:
            print("Tentando:", label)
            action()
            clicked = True
            break
        except Exception as e:
            print("Falhou:", label)

    # Espera algum redirect/URL mudar
    try:
        page.wait_for_timeout(2500)
    except Exception:
        pass

    snap(page, "02_after_click.png")

    # Às vezes abre em NOVA ABA. Vamos checar.
    pages = context.pages
    if len(pages) > 1:
        page = pages[-1]
        print("Nova aba detectada. Mudando para ela.")
        snap(page, "03_new_tab.png")

    # Agora vamos tentar ir DIRETO para a página de pesquisa (às vezes só funciona depois do “anon”)
    search_url = "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp"
    print("Indo para a página de pesquisa…")
    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    snap(page, "04_search_page.png")

    input("Deixei tudo aberto. Aperte ENTER aqui no terminal para fechar…")
    browser.close()
