# Licitații imobiliare — executori judecătorești

Pagină statică (GitHub Pages) care adună anunțurile din categoria „Apartament” de pe
[REPES](https://prod.executori.ro/repes/) (registrul de publicitate al executorilor judecătorești, UNEJ):

- prețul de pornire și valoarea de evaluare, citite din publicația PDF a fiecărei licitații;
- termenul licitației (I = 100%, II = 75%, III = 50% din evaluare);
- locația pe hartă și link Google Maps / Street View;
- distanța până la cea mai apropiată stație de metrou (București);
- 2–3 anunțuri similare de pe storia.ro și prețul median pe mp din zonă;
- semnale de risc detectate automat (cotă-parte, uzufruct, TVA, debitor decedat).

Publicațiile PDF nu sunt copiate aici: butonul „Descarcă publicația” le descarcă direct de la sursă (REPES).

Estimările de piață și de profit sunt orientative. Verifică întotdeauna publicația completă și zona înainte de a licita.

## Actualizare zilnică

Workflow-ul `.github/workflows/daily.yml` rulează în fiecare dimineață (și manual, din tab-ul Actions → „Actualizare zilnică” → Run workflow):

1. `pipeline/fetch.py` – citește toate anunțurile „Apartament” din API-ul REPES și descarcă doar publicațiile noi sau schimbate;
2. `pipeline/ocr.py` – extrage textul din PDF-uri (Tesseract); PDF-urile se șterg după;
3. `pipeline/parse.py`, `market.py` – evaluare, termen, suprafață, riscuri, corecții verificate manual (`pipeline/overrides.json`);
4. `pipeline/geocode.py`, `geo.py` – poziție precisă din adresa publicației, distanța la metrou;
5. `pipeline/zone.py` – cartierul și 3 anunțuri comparabile active de pe storia.ro (reîmprospătate săptămânal);
6. `pipeline/build.py` – `data.json` pentru site, cu cursul oficial BNR al zilei;
7. `pipeline/history.py` – `history.json`: când a apărut fiecare licitație, schimbări de preț/termen/dată, licitații ieșite.

Textul publicațiilor (care conține date personale ale debitorilor) și cache-urile stau doar în cache-ul privat al GitHub Actions, nu în repo.

Rulare locală: `WORK=work ./pipeline/run_daily.sh` (necesită `tesseract` și `pip install pymupdf`).
