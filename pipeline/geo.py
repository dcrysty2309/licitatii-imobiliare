import json, sys, math, re
from collections import Counter
BASE = sys.argv[1]
src = sys.argv[2] if len(sys.argv) > 2 else 'rows2.json'
api = {e['id'][:8]: e for e in json.load(open(BASE + '/apts_all.json'))}
from common import HERE
import os
wd = json.load(open(os.path.join(HERE, 'metro_wikidata.json')))['results']['bindings']
metro = []
for b in wd:
    m = re.match(r'Point\(([-\d.]+) ([-\d.]+)\)', b['coord']['value'])
    metro.append((re.sub(r'\s*\(stați[ea] de metrou\)', '', b['sLabel']['value']), float(m.group(2)), float(m.group(1))))
def hav(a, b, c, d):
    R = 6371000; p1, p2 = math.radians(a), math.radians(c); dp = p2 - p1; dl = math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))
rows = json.load(open(BASE + '/' + src))
PREC = json.load(open(BASE + '/geo/precise.json')) if os.path.exists(BASE + '/geo/precise.json') else {}
def decimals(g):
    la, ln = g.split(',')
    return min(len(la.split('.')[1]) if '.' in la else 0, len(ln.split('.')[1]) if '.' in ln else 0)
gps_count = Counter()
for r in rows:
    e = api.get(r['id'][:8])
    g = (e['asset']['address'].get('gpsLocation') or '') if e else ''
    bej = ((e.get('address') or {}).get('gpsLocation') or '') if e else ''
    r['lat'] = r['lng'] = None
    if g:
        la, ln = map(float, g.split(','))
        r['lat'], r['lng'] = round(la, 6), round(ln, 6)
        gps_count[(round(la, 4), round(ln, 4))] += 1
    r['gps_bej'] = bool(g and g == bej)
    r['street'] = e['asset']['address'].get('street') if e else ''
for r in rows:
    if r['lat'] is None: r['gps_q'] = 'lipsa'; continue
    e = api.get(r['id'][:8])
    g = e['asset']['address'].get('gpsLocation') if e else ''
    p = PREC.get(r['id'][:8])
    if p and 'lat' not in p: p = None
    r['geo_label'] = p['label'] if p else None
    if p and p['q'] in ('bloc', 'numar'):
        r['lat'], r['lng'] = p['lat'], p['lng']
        r['gps_q'] = 'adresa'
    elif g and decimals(g) >= 4 and not r['gps_bej']:
        r['gps_q'] = 'adresa'
    elif p and p['q'] == 'strada':
        r['lat'], r['lng'] = p['lat'], p['lng']
        r['gps_q'] = 'strada'
    elif r['gps_bej']:
        r['gps_q'] = 'birou executor (nu e locatia reala)'
    else:
        r['gps_q'] = 'aproximativ (localitate)'
    r['metro'] = None
    if r['lat'] and r['gps_q'] in ('adresa', 'strada') and 44.30 < r['lat'] < 44.60 and 25.90 < r['lng'] < 26.35:
        d, name = min((hav(r['lat'], r['lng'], la, ln), n) for n, la, ln in metro)
        r['metro'] = {'name': name, 'm': int(round(d, -1)), 'walk_min': int(round(d * 1.3 / 80))}
json.dump(rows, open(BASE + '/' + src.replace('.json', '_geo.json'), 'w'), ensure_ascii=False)
print(Counter(r['gps_q'] for r in rows))
for r in rows:
    if r['metro'] and r['kind'] == 'apartament': print(r['city'], r['start_eur'], r['metro'], r['gps_q'], r['name'][:40])
