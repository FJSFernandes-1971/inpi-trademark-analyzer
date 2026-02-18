from inpi_fetch import fetch_inpi_by_class

recs = fetch_inpi_by_class("solano", "30", headless=True)

print("Qtd:", len(recs))
for r in recs[:10]:
    print(r)
