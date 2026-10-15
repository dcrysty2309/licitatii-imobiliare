"""Coordonate precise din adresa scrisa in publicatie (Nominatim), pentru anunturile REPES
cu GPS rotunjit (sub 4 zecimale). Rezultat: repes/geo/precise.json {id8: {lat, lng, q, label}}."""
import json, os, re, sys, time, hashlib, subprocess, urllib.parse, unicodedata

BASE = sys.argv[1]
NCACHE = os.path.join(BASE, 'geo', 'nominatim'); os.makedirs(NCACHE, exist_ok=True)
NUA = 'radar-licitatii/1.0 (personal research; github.com/dcrysty2309/licitatii-imobiliare)'

def get(url):
    p = os.path.join(NCACHE, hashlib.md5(url.encode()).hexdigest() + '.raw')
    if os.path.exists(p): return open(p, encoding='utf-8').read()
    out = subprocess.run(['curl', '-s', '-m', '30', '-A', NUA, url], capture_output=True, text=True).stdout
    open(p, 'w', encoding='utf-8').write(out); time.sleep(1.1)
    return out

def decimals(g):
    la, ln = g.split(',')
    return min(len(la.split('.')[1]) if '.' in la else 0, len(ln.split('.')[1]) if '.' in ln else 0)

def clean_city(c):
    c = c or ''
    if re.match(r'(?i)sectorul', c): return 'București'
    return c

def search(params):
    url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=ro&addressdetails=1&' + urllib.parse.urlencode(params)
    try:
        r = json.loads(get(url))
        return r[0] if r else None
    except Exception:
        return None

api = json.load(open(os.path.join(BASE, 'apts_all.json')))
out = {}
for e in api:
    a = e['asset']['address']
    g = a.get('gpsLocation')
    if g and decimals(g) >= 4: continue
    city = clean_city(a.get('city'))
    county = a.get('county') or ''
    orig = (a.get('originalAddress') or '').replace('⍽', ' ')
    street = a.get('street') or ''
    m = re.search(r'(?:nr\.?\s*)?(\d+[A-Za-z]?)\b', orig.split(',')[0]) if street else None
    number = a.get('streetNo') or (m.group(1) if m and not re.search(r'\d', street) else None)
    hit, q = None, None
    if street:
        hit = search({'street': f'{number} {street}' if number else street, 'city': city, 'county': county, 'country': 'Romania'})
        if hit: q = 'numar' if number and hit.get('addresstype') in ('building', 'house', 'place') or (hit.get('address') or {}).get('house_number') else 'strada'
        if not hit and number:
            hit = search({'street': street, 'city': city, 'county': county, 'country': 'Romania'}); q = 'strada' if hit else None
    if not hit and orig:
        hit = search({'q': orig}); q = 'adresa (aprox.)' if hit else None
    if hit:
        out[e['id'][:8]] = {'lat': round(float(hit['lat']), 6), 'lng': round(float(hit['lon']), 6), 'q': q, 'label': hit.get('display_name', '')[:160]}
json.dump(out, open(os.path.join(BASE, 'geo', 'precise.json'), 'w'), ensure_ascii=False, indent=0)
from collections import Counter
print('geocoded', len(out), Counter(v['q'] for v in out.values()))
