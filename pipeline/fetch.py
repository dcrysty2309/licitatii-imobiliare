"""Pasul 1: citeste toate anunturile din categoria Apartament de pe REPES si descarca
doar publicatiile noi sau schimbate (un termen nou de licitatie vine cu alta publicatie).

work/apts_all.json   lista completa, asa cum vine din API
work/pubmeta.json    {id: publicationFile} pentru publicatiile deja citite
work/pubs/<id>.pdf   publicatiile de citit cu OCR (se sterg dupa OCR)
"""
import json, os, sys, time, subprocess
from common import TODAY

WORK = sys.argv[1]
API = 'https://prod.executori.ro/repes/api/auctions'
UA = 'Mozilla/5.0 (radar-licitatii; github.com/dcrysty2309/licitatii-imobiliare)'
os.makedirs(os.path.join(WORK, 'pubs'), exist_ok=True)
os.makedirs(os.path.join(WORK, 'txt'), exist_ok=True)

def post(page):
    url = f'{API}?searchText=&exactMatch=false&pageSize=16&page={page}&currency=RON&sortParams=NEWEST'
    for attempt in range(4):
        r = subprocess.run(['curl', '-s', '-m', '60', '-A', UA, '-H', 'Content-Type: application/json', '-X', 'POST', url,
                            '-d', '{"genericParams":{"category":"APT","type":"IMO"}}'], capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f'REPES nu raspunde (pagina {page})')

first = post(1)
total = first['totalCount']
entries = {e['id']: e for e in first['entries']}
page = 2
while (page - 1) * 16 < total + 16 and page < 200:
    d = post(page)
    if not d['entries']: break
    for e in d['entries']: entries[e['id']] = e
    page += 1
    time.sleep(0.3)
if len(entries) < 0.5 * total:
    raise SystemExit(f'Lista REPES incompleta: {len(entries)} din {total}')
json.dump(list(entries.values()), open(os.path.join(WORK, 'apts_all.json'), 'w'), ensure_ascii=False)
print(f'REPES: {len(entries)} anunturi (totalCount {total})')

meta_path = os.path.join(WORK, 'pubmeta.json')
meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
new = 0
for e in entries.values():
    if e['date'][:10] < TODAY: continue
    pid = e.get('publicationFile')
    txt = os.path.join(WORK, 'txt', e['id'] + '.txt')
    if meta.get(e['id']) == pid and os.path.exists(txt) and os.path.getsize(txt) > 0:
        continue
    if os.path.exists(txt): os.remove(txt)  # publicatie schimbata: o citim din nou
    pdf = os.path.join(WORK, 'pubs', e['id'] + '.pdf')
    subprocess.run(['curl', '-s', '-m', '90', '-A', UA, '-o', pdf, f"{API}/{e['caseId']}/{e['id']}/publication/"])
    if os.path.exists(pdf) and os.path.getsize(pdf) > 1000:
        meta[e['id']] = pid
        new += 1
    time.sleep(0.3)
json.dump(meta, open(meta_path, 'w'))
print(f'publicatii noi sau schimbate descarcate: {new}')
