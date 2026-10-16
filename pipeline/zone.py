"""Analiza de zona pentru fiecare apartament de la licitatie.

1. cartierul: reverse geocoding (Nominatim) + potrivire cu lista de cartiere storia.ro a orasului
   (daca nu se potriveste dupa nume: cel mai apropiat centru de cartier geocodat)
2. pool de anunturi storia.ro in cartier (camere + suprafata apropiata), fallback oras
3. fiecare candidat e deschis: coordonate, status 'active', data ultimei modificari (<= 120 zile)
4. alege 3 cele mai apropiate (distanta reala in metri) + statistica zonei (median, P25-P75, n)
"""
import json, re, sys, os, time, math, hashlib, subprocess, statistics, unicodedata, urllib.parse
from datetime import datetime, timezone
from common import TODAY, TTL_DAYS

BASE = sys.argv[1]
CACHE = os.path.join(BASE, 'comps', 'cache'); os.makedirs(CACHE, exist_ok=True)
NCACHE = os.path.join(BASE, 'geo', 'nominatim'); os.makedirs(NCACHE, exist_ok=True)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36'
NUA = 'radar-licitatii/1.0 (personal research; github.com/dcrysty2309/licitatii-imobiliare)'
ROOMS = {1: 'ONE', 2: 'TWO', 3: 'THREE', 4: 'FOUR'}
NOW = datetime.fromisoformat(TODAY).replace(tzinfo=timezone.utc)
BLOCKED = {'n': 0}
MAX_AGE_DAYS = 120
DETAILS_PER_AUCTION = 20
RADIUS_M = 1500
NEWBUILD = re.compile(r'constructie|finalizare|bloc-nou|ansamblu|dezvoltator|predare|proiect-nou|comision-0|rezidential|residence|202[6-8]')

def slug(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower().strip()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')

def hav(a, b, c, d):
    R = 6371000; p1, p2 = math.radians(a), math.radians(c); dp = p2 - p1; dl = math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))

def curl(url, ua, cache_dir, delay):
    h = hashlib.md5(url.encode()).hexdigest()
    p = os.path.join(cache_dir, h + '.raw')
    if os.path.exists(p):
        return open(p, encoding='utf-8', errors='ignore').read()
    r = subprocess.run(['curl', '-sL', '-m', '40', '-A', ua, url], capture_output=True, text=True)
    open(p, 'w', encoding='utf-8').write(r.stdout)
    time.sleep(delay)
    return r.stdout

def jcache(url, fetch_fn):
    """Cache JSON cu expirare (TTL_DAYS). Nu salveaza nimic daca raspunsul nu a putut fi citit."""
    p = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + '.json')
    if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < TTL_DAYS * 86400:
        return json.load(open(p))
    val = fetch_fn()
    if val is None:
        BLOCKED['n'] += 1
        return json.load(open(p)) if os.path.exists(p) else None
    json.dump(val, open(p, 'w'), ensure_ascii=False)
    return val

def fetch_raw(url, delay):
    r = subprocess.run(['curl', '-sL', '-m', '40', '-A', UA, url], capture_output=True, text=True)
    time.sleep(delay)
    return r.stdout

def next_data(html):
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m: return None
    try: return json.loads(m.group(1))['props']['pageProps']
    except Exception: return None

# ---------- storia ----------
def search(loc, rooms=None, amin=None, amax=None):
    q = []
    if rooms in ROOMS: q.append('roomsNumber=%5B' + ROOMS[rooms] + '%5D')
    if amin: q.append(f'areaMin={amin}&areaMax={amax}')
    q.append('limit=72')
    url = f'https://www.storia.ro/ro/rezultate/vanzare/apartament/{loc}?' + '&'.join(q)
    def _f():
        pp = next_data(fetch_raw(url, 1.0))
        if pp is None: return None
        d = pp.get('data') or {}
        KEEP = ('slug', 'title', 'areaInSquareMeters', 'roomsNumber', 'floorNumber', 'totalPrice', 'dateCreated', 'pushedUpAt', 'investmentState', 'development')
        sa = d.get('searchAds') or {}
        items = []
        for x in sa.get('items') or []:
            y = {k: x.get(k) for k in KEEP}
            y['location'] = {'reverseGeocoding': {'locations': [{'id': l.get('id')} for l in ((x.get('location') or {}).get('reverseGeocoding') or {}).get('locations') or []]}}
            items.append(y)
        rel = [{'name': i.get('name'), 'location': i.get('location')} for i in ((d.get('searchLinksRelatedLocations') or {}).get('items') or [])]
        return {'searchAds': {'items': items}, 'searchLinksRelatedLocations': {'items': rel}}
    data = jcache(url, _f) or {}
    sa = data.get('searchAds') or {}
    items = []
    for x in (sa.get('items') or []):
        locs = [l['id'] for l in ((x.get('location') or {}).get('reverseGeocoding') or {}).get('locations') or []]
        if not any(l == loc or l.startswith(loc + '/') for l in locs): continue
        price = (x.get('totalPrice') or {}); area = x.get('areaInSquareMeters')
        if not (price.get('value') and area and price.get('currency') == 'EUR'): continue
        if x.get('investmentState') or x.get('development') or NEWBUILD.search(slug(x.get('title') or '')): continue
        items.append(dict(url='https://www.storia.ro/ro/oferta/' + x['slug'], title=x.get('title'), area=area,
                          rooms=x.get('roomsNumber'), floor=x.get('floorNumber'), price=price['value'],
                          ppm=price['value'] / area, district=next((l for l in locs if l.count('/') >= 2), None),
                          created=x.get('dateCreated'), pushed=x.get('pushedUpAt')))
    rel = [(i['name'], i['location']) for i in ((data.get('searchLinksRelatedLocations') or {}).get('items') or [])]
    seen, uniq = set(), []
    for i in items:
        if i['url'] in seen: continue
        seen.add(i['url']); uniq.append(i)
    return url, uniq, rel

def ad_detail(url):
    def _f():
        pp = next_data(fetch_raw(url, 0.8))
        if pp is None: return None
        ad = pp.get('ad') or {}
        co = (ad.get('location') or {}).get('coordinates') or {}
        return dict(status=ad.get('status'), modified=ad.get('modifiedAt') or ad.get('createdAt'),
                    lat=co.get('latitude'), lng=co.get('longitude'))
    return jcache(url, _f) or dict(status=None, modified=None, lat=None, lng=None)

def age_days(ts):
    if not ts: return None
    try:
        t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if t.tzinfo is None: t = t.replace(tzinfo=timezone.utc)
        return (NOW - t).days
    except Exception: return None

# ---------- nominatim ----------
def nom_reverse(lat, lng):
    url = f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&addressdetails=1&accept-language=ro&lat={lat}&lon={lng}'
    try: return json.loads(curl(url, NUA, NCACHE, 1.1))
    except Exception: return {}

def nom_search(q):
    url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=ro&q=' + urllib.parse.quote(q)
    try:
        r = json.loads(curl(url, NUA, NCACHE, 1.1))
        return (float(r[0]['lat']), float(r[0]['lon'])) if r else None
    except Exception: return None

def tokens(s): return set(t for t in slug(s).split('-') if len(t) > 2)

def match_district(lat, lng, related, city_name):
    """related: [(name, loc_id)] of storia districts of the city. Returns (name, loc_id, how)."""
    if not related: return None
    rv = nom_reverse(lat, lng).get('address') or {}
    names = [rv.get(k) for k in ('neighbourhood', 'quarter', 'suburb', 'residential', 'city_district', 'hamlet') if rv.get(k)]
    for n in names:
        tn = tokens(n)
        for name, lid in related:
            td = tokens(name) | tokens(lid.split('/')[-1])
            if tn and td and (tn & td): return name, lid, f'nume ({n})'
    # nearest geocoded district centre
    best = None
    for name, lid in related:
        c = nom_search(f'{name}, {city_name}, Romania')
        if not c: continue
        d = hav(lat, lng, c[0], c[1])
        if d < 3000 and (best is None or d < best[0]): best = (d, name, lid)
    if best: return best[1], best[2], f'cel mai apropiat centru ({int(best[0])} m)'
    return None

# ---------- main ----------
rows = json.load(open(os.path.join(BASE, 'rows2_geo.json')))  # coordonate corectate de geo.py
targets = [r for r in rows if r['kind'] == 'apartament' and r['date'][:10] >= TODAY
           and not (r['flags'].startswith('cota-parte') and 'verifica' not in r['flags']) and 'EXCLUS' not in r['flags']]
ONLY = sys.argv[2].split(',') if len(sys.argv) > 2 else None
if ONLY: targets = [r for r in targets if r['id'][:8] in ONLY]
print('targets', len(targets), flush=True)
done = 0
for r in rows:
    r['zone'] = None
PREV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data.json')
PREV = {}
if os.path.exists(PREV_PATH):
    try:
        _d = json.load(open(PREV_PATH))
        _upd = _d.get('updated', '')
        for o in _d['rows']:
            z = o.get('zone')
            if z and z.get('status') == 'ok':
                if not z.get('computed') and _upd:
                    dd, mm, yy = _upd.split('.'); z['computed'] = f'{yy}-{mm}-{dd}'
                PREV[o['id']] = z
    except Exception as ex:
        print('nu pot citi data.json anterior:', ex)
reused = 0
for r in targets:
    pz = PREV.get(r['id'][:8])
    if pz and pz.get('computed') and (NOW - datetime.fromisoformat(pz['computed']).replace(tzinfo=timezone.utc)).days < TTL_DAYS:
        r['zone'] = pz; reused += 1; continue
    county, city = slug(r['county']), slug(r['city'])
    if county == 'bucuresti':
        city_loc = f'bucuresti/{city}' if city.startswith('sectorul') else 'bucuresti'
        city_name = 'București'
    else:
        city_loc, city_name = f'{county}/{city}', r['city']
    sq, rm = r['sqm'], r['rooms']
    amin, amax = (int(sq * 0.75), int(sq * 1.3) + 1) if sq else (None, None)
    precise = r.get('gps_q') in ('adresa', 'strada') and r.get('lat') is not None

    # cartierul
    _, city_items, related = search(city_loc, rm)
    district = match_district(r['lat'], r['lng'], related, city_name) if precise and related else None

    # pool: cartier -> oras
    pool, level, pool_url = [], None, None
    tries = []
    if district: tries += [(district[1], rm, amin, amax), (district[1], rm, None, None), (district[1], None, amin, amax)]
    tries += [(city_loc, rm, amin, amax), (city_loc, rm, None, None), (city_loc, None, amin, amax)]
    for loc, rr, a1, a2 in tries:
        if rr is None and a1 is None: continue
        url, items, _ = search(loc, rr, a1, a2)
        if len(items) >= 3:
            pool, pool_url = items, url
            level = 'cartier' if district and loc == district[1] else ('sector' if loc.startswith('bucuresti/') else 'oras')
            break
    if not pool:
        r['zone'] = {'status': 'fara anunturi comparabile pe storia.ro', 'district': district[0] if district else None}
        continue

    # statistica zonei (anunturile din cautare sunt active), fara extreme; daca e mica, largesc la toate camerele
    stat_pool = list(pool)
    if len(stat_pool) < 8 and amin:
        _, wider, _ = search(pool_url.split('/apartament/')[1].split('?')[0], None, amin, amax)
        urls = {i['url'] for i in stat_pool}
        stat_pool += [i for i in wider if i['url'] not in urls]
    ppms = sorted(i['ppm'] for i in stat_pool)
    med = statistics.median(ppms)
    clean = [p for p in ppms if 0.5 * med <= p <= 2 * med]
    q = statistics.quantiles(clean, n=4) if len(clean) >= 4 else [min(clean), statistics.median(clean), max(clean)]

    # verificare anunturi: deschid candidatii cei mai apropiati ca suprafata
    cand = sorted([i for i in pool if 0.5 * med <= i['ppm'] <= 2 * med], key=lambda i: abs(i['area'] - sq) if sq else 0)[:DETAILS_PER_AUCTION]
    checked = []
    for i in cand:
        d = ad_detail(i['url'])
        age = age_days(d['modified'])
        if d['status'] != 'active' or age is None or age > MAX_AGE_DAYS: continue
        dist = int(hav(r['lat'], r['lng'], d['lat'], d['lng'])) if (precise and d['lat']) else None
        checked.append(dict(i, dist=dist, age=age, modified=(d['modified'] or '')[:10]))
    if precise:
        checked.sort(key=lambda i: (i['dist'] is None, i['dist'] or 0))
    near = [i for i in checked if i['dist'] is not None and i['dist'] <= RADIUS_M]
    scope = 'larg'
    if precise and len(near) >= 3:
        # mediana doar din anunturile active din raza de 1,5 km
        nppm = sorted(i['ppm'] for i in near)
        clean = nppm
        q = statistics.quantiles(nppm, n=4) if len(nppm) >= 4 else [min(nppm), statistics.median(nppm), max(nppm)]
        scope = 'raza'
    picks = (near if precise and near else checked)[:3]

    city_slug_olx = 'bucuresti' if county == 'bucuresti' else city
    olx_q = slug(district[0]) if district else ''
    olx = f'https://www.olx.ro/imobiliare/apartamente-garsoniere-de-vanzare/{city_slug_olx}/' + (f'q-{olx_q}/' if olx_q else '')
    r['zone'] = {
        'status': 'ok', 'level': level, 'district': district[0] if district else None, 'match': district[2] if district else None,
        'n': len(clean), 'median_ppm': round(statistics.median(clean)), 'p25': round(q[0]), 'p75': round(q[-1]),
        'search_url': pool_url, 'olx_url': olx, 'checked': len(cand), 'active_ok': len(checked),
        'computed': TODAY, 'scope': scope, 'radius_m': RADIUS_M, 'n_near': len(near), 'precise': precise,
        'items': [{k: i[k] for k in ('url', 'title', 'area', 'rooms', 'floor', 'price', 'dist', 'age', 'modified')} for i in picks],
    }
    done += 1
    if done % 10 == 0: print(done, flush=True)

json.dump(rows, open(os.path.join(BASE, 'rows4_test.json' if ONLY else 'rows4.json'), 'w'), ensure_ascii=False)
from collections import Counter
print('zone refolosite:', reused, '| raspunsuri blocate:', BLOCKED['n'], flush=True)
print('DONE', Counter((r['zone'] or {}).get('status') for r in targets), Counter((r['zone'] or {}).get('level') for r in targets), flush=True)
