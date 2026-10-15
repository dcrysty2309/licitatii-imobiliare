"""Pozitia exacta a blocului, pornind de la adresa scrisa in publicatie.

Pentru fiecare licitatie (cu adresa extrasa din publicatie sau, altfel, cu adresa REPES):
  1. strada + numar (Nominatim, OpenStreetMap)
  2. numele vechi al strazii ("fosta ...") + numar
  3. blocul ("Bloc C3, strada, oras") - multe blocuri sunt in OpenStreetMap cu nume
  4. Photon (alt geocoder pe date OpenStreetMap, mai tolerant la scriere)
  5. doar strada, daca nu se gaseste cladirea
Rezultat: work/geo/precise.json {id8: {lat, lng, q: bloc|numar|strada, label, street_alt}}
"""
import json, os, re, sys, time, hashlib, subprocess, urllib.parse, unicodedata

WORK = sys.argv[1]
NCACHE = os.path.join(WORK, 'geo', 'nominatim'); os.makedirs(NCACHE, exist_ok=True)
NUA = 'radar-licitatii/1.0 (personal research; github.com/dcrysty2309/licitatii-imobiliare)'

def get(url, delay):
    p = os.path.join(NCACHE, hashlib.md5(url.encode()).hexdigest() + '.raw')
    if os.path.exists(p): return open(p, encoding='utf-8').read()
    out = subprocess.run(['curl', '-s', '-m', '30', '-A', NUA, url], capture_output=True, text=True).stdout
    if out.strip().startswith(('[', '{')): open(p, 'w', encoding='utf-8').write(out)
    time.sleep(delay)
    return out

def n(s): return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()

def nom(params):
    url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=3&countrycodes=ro&addressdetails=1&namedetails=1&' + urllib.parse.urlencode(params)
    try: return json.loads(get(url, 1.1)) or []
    except Exception: return []

def photon(q):
    url = 'https://photon.komoot.io/api/?limit=3&q=' + urllib.parse.quote(q)
    try: return (json.loads(get(url, 0.6)) or {}).get('features') or []
    except Exception: return []

STREET = re.compile(r'(?i)\b(str(?:ada)?|bd|b-dul|bdul|bulevardul|calea|aleea|al|[sș]os(?:eaua)?|intrarea|drumul|splaiul|pia[tț]a|p-ta)\b\.?\s*([^,;]+?)\s*(?=,|;|\bnr\b|\bnum[aă]rul\b|$)')
NR = re.compile(r'(?i)\b(?:nr|num[aă]rul)\b\.?\s*:?\s*(\d+\s?[A-Za-z]?)\b')
BL = re.compile(r'(?i)\b(?:bl|blocul)\b\.?\s*([A-Za-z0-9][A-Za-z0-9\-]{0,5})\b')
FOSTA = re.compile(r'(?i)\(\s*fost[ae]?\s+(?:str(?:ada)?\.?\s*)?([^)]+)\)')

def parts(addr):
    a = addr or ''
    alt = FOSTA.search(a)
    alt = alt.group(1).strip() if alt else None
    a2 = FOSTA.sub('', a)
    st = STREET.search(a2)
    street = re.sub(r'\s+', ' ', st.group(2)).strip(' .') if st else None
    if street and re.match(r'(?i)^(nr|bl|sc)\b', street): street = None
    nr = NR.search(a2); bl = BL.search(a2)
    return street, alt, (nr.group(1).replace(' ', '') if nr else None), (bl.group(1) if bl else None)

def city_of(r):
    c = r['city'] or ''
    if re.match(r'(?i)sectorul', c) or n(c) == 'bucuresti': return 'București'
    return c

def same_city(res_addr, city):
    blob = n(' '.join(str(v) for v in (res_addr or {}).values()))
    return n(city).split(' ')[0] in blob

def is_building(x):
    return x.get('addresstype') in ('building', 'house', 'place') or (x.get('address') or {}).get('house_number')

rows = json.load(open(os.path.join(WORK, 'rows.json')))
api = {e['id'][:8]: e for e in json.load(open(os.path.join(WORK, 'apts_all.json')))}
out = {}
for r in rows:
    if r['kind'] not in ('apartament', 'casa'): continue
    rid = r['id'][:8]
    e = api.get(rid) or {}
    addr = r.get('addr_pub') or (e.get('asset', {}).get('address') or {}).get('originalAddress') or ''
    street, alt, nr, bl = parts(addr)
    if not street and e:
        street = (e['asset']['address'].get('street') or '').strip() or None
        street = re.sub(r'(?i)^(strada|str\.?)\s*', '', street) if street else None
    city, county = city_of(r), r['county']
    if not street: continue
    hit, q = None, None
    names = [street] + ([alt] if alt else [])
    # ce nume de strada exista efectiv pe harta in orasul respectiv (strazi redenumite)
    osm_street = None
    if alt:
        for s in names:
            if any(same_city(x.get('address'), city) for x in nom({'street': s, 'city': city, 'county': '' if city == 'București' else county, 'country': 'Romania'})):
                osm_street = s; break
    # 1-2. strada (sau numele vechi) + numar
    for s in names:
        if hit or not nr: break
        for x in nom({'street': f'{nr} {s}', 'city': city, 'county': '' if city == 'București' else county, 'country': 'Romania'}):
            if is_building(x) and same_city(x.get('address'), city): hit, q = x, 'numar'; break
    # 3. blocul
    if not hit and bl:
        for s in names:
            for x in nom({'q': f'Bloc {bl}, {s}, {city}'}):
                nm = n((x.get('namedetails') or {}).get('name') or x.get('name') or '')
                if is_building(x) and same_city(x.get('address'), city) and n(bl) in nm.replace(' ', ''):
                    hit, q = x, 'bloc'; break
            if hit: break
    # 4. Photon
    if not hit and nr:
        for s in names:
            for f in photon(f'{s} {nr}, {city}'):
                pr = f.get('properties') or {}
                if pr.get('housenumber') and n(pr.get('housenumber')) == n(nr) and n(city).split(' ')[0] in n(pr.get('city') or pr.get('county') or pr.get('state') or ''):
                    lon, lat = f['geometry']['coordinates']
                    hit, q = {'lat': lat, 'lon': lon, 'display_name': f"{pr.get('street', '')} {pr.get('housenumber', '')}, {pr.get('city', '')}"}, 'numar'; break
            if hit: break
    # 5. doar strada
    if not hit:
        for s in names:
            for x in nom({'street': s, 'city': city, 'county': '' if city == 'București' else county, 'country': 'Romania'}):
                if same_city(x.get('address'), city): hit, q = x, 'strada'; break
            if hit: break
    if hit:
        out[rid] = {'lat': round(float(hit['lat']), 6), 'lng': round(float(hit['lon']), 6), 'q': q,
                    'label': (hit.get('display_name') or '')[:160], 'street_alt': alt, 'street': street, 'nr': nr, 'bl': bl, 'osm_street': osm_street}
    elif osm_street:
        out[rid] = {'q': 'nume', 'osm_street': osm_street, 'street': street, 'street_alt': alt}
json.dump(out, open(os.path.join(WORK, 'geo', 'precise.json'), 'w'), ensure_ascii=False, indent=0)
from collections import Counter
print('geocodare:', len(out), dict(Counter(v['q'] for v in out.values())))
