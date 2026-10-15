import json, sys
BASE, OUT = sys.argv[1], sys.argv[2]
rows = json.load(open(BASE + '/rows4.json'))
from common import TODAY
import os as _os
# analiza zonei din ziua precedenta: o pastram daca azi storia.ro nu a raspuns
PREV = {}
if _os.path.exists(OUT):
    try: PREV = {o['id']: o for o in json.load(open(OUT))['rows']}
    except Exception: PREV = {}
for r in rows:
    z = r.get('zone'); p = PREV.get(r['id'][:8])
    if (not z or z.get('status') != 'ok') and p and (p.get('zone') or {}).get('status') == 'ok':
        r['zone'] = dict(p['zone'], stale=True)
ASK2SALE = 0.93
import re as _re, subprocess as _sp
_x = _sp.run(['curl', '-sL', '-m', '30', 'https://curs.bnr.ro/nbrfxrates.xml'], capture_output=True, text=True).stdout
RATE = float(_re.search(r'currency="EUR">([\d.]+)<', _x).group(1))
RATE_DATE = _re.search(r'<Cube date="([\d-]+)"', _x).group(1)
print('BNR EUR', RATE, RATE_DATE)
api = {e['id']: e for e in json.load(open(BASE + '/apts_all.json'))}
PRECISE = json.load(open(BASE + '/geo/precise.json')) if _os.path.exists(BASE + '/geo/precise.json') else {}
import unicodedata as _ud
def _n(x): return _ud.normalize('NFKD', x or '').encode('ascii', 'ignore').decode().lower()
def maps_query(e, pub=None):
    a = (e or {}).get('asset', {}).get('address') or {}
    orig = (pub or a.get('originalAddress') or '').replace('\u237d', ' ')
    orig = _re.sub(r'(?i)\bnum[aă]rul\s*', 'nr. ', orig)
    orig = _re.sub(r'^[^A-Za-zĂÂÎȘŞȚŢăâîșşțţ]+', '', orig)
    orig = _re.sub(r"['’`]", '', orig)
    orig = _re.sub(r'\s*\((fost[ae]?|fosta|fost)[^)]*\)', '', orig, flags=_re.I)
    orig = _re.sub(r',?\s*(Romania|România)\s*$', '', orig, flags=_re.I)
    orig = _re.sub(r'(?i),?\s*\b(bl|blocul|sc|scara|et|etaj|etajul|ap|apartament|apartamentul|cam|parter)\b\.?\s*[\w-]*', '', orig)
    orig = _re.sub(r'\s{2,}', ' ', orig).strip(' ,-')
    city, county = a.get('city') or '', a.get('county') or ''
    m = _re.match(r'(?i)sectorul\s*(\d)', city)
    place = (f'Sector {m.group(1)}' if 'bucuresti' in _n(orig) else f'Sector {m.group(1)}, București') if m else city
    parts = [orig] if orig else []
    if place and _n(city.replace('Sectorul', '')).strip() not in _n(orig) and _n(place) not in _n(orig):
        parts.append(place)
    if county and not m and _n(county) not in _n(', '.join(parts)) and _n(county) != _n(city):
        parts.append('județul ' + county)
    parts.append('România')
    return ', '.join(p for p in parts if p)
out = []
for r in rows:
    if r['cur'] == 'RON' and r['start']:
        r['start_eur'] = round(r['start'] / RATE)
        if r.get('eval'): r['eval_eur'] = round(r['eval'] / RATE)
    if r.get('sqm') and r['start_eur']: r['eur_m2'] = round(r['start_eur'] / r['sqm'])
    c = r.get('comps')
    z = r.get('zone')
    if z and z.get('status') == 'ok':
        ppm, src = z['median_ppm'], 'zona'
    elif c and c.get('status') == 'ok' and c.get('level') != 'judet':
        ppm, src = c['median_ppm'], 'storia'
    elif r['kind'] == 'apartament':
        ppm, src = r['mkt_m2'], 'estimare'
    else:
        ppm, src = None, None
    mv = profit = vs = None
    partial = 'cota-parte' in (r['flags'] or '') or 'EXCLUS' in (r['flags'] or '')
    if ppm and r['sqm'] and r['kind'] == 'apartament' and not partial:
        mv = r['sqm'] * ppm * ASK2SALE
        reno = max(4000, r['sqm'] * 220)
        profit = round(mv - r['start_eur'] - reno - r['start_eur'] * 0.02 - mv * 0.05)
        vs = round(100 * r['start_eur'] / mv)
        mv = round(mv)
    o = {k: r.get(k) for k in ('date', 'county', 'city', 'addr', 'name', 'desc', 'rooms', 'sqm', 'cur', 'start', 'start_eur',
                               'eval_eur', 'term', 'discount', 'eur_m2', 'flags', 'kind', 'note', 'link', 'pdf', 'lat', 'lng', 'gps_q', 'metro', 'comps', 'zone')}
    e = api.get(r['id'])
    pics = (e or {}).get('asset', {}).get('pictures') or []
    g = ((e or {}).get('asset', {}).get('guarantee') or {})
    gv = g.get('value')
    o['guar'] = gv
    o['guar_eur'] = None if gv is None else round(gv if g.get('currency') == 'EUR' else gv / RATE)
    o['addr_pub'] = r.get('addr_pub')
    o['maps_q'] = maps_query(e, r.get('addr_pub'))
    pg = PRECISE.get(r['id'][:8]) or {}
    if pg.get('street_alt') and pg.get('q') != 'numar':
        # hartile cunosc adesea doar numele vechi al strazii ("fosta ...")
        o['maps_q'] = f"Strada {pg['street_alt']}{' ' + pg['nr'] if pg.get('nr') else ''}, " + o['maps_q'].split(', ', 1)[-1] if ', ' in o['maps_q'] else o['maps_q']
    o['geo_label'] = r.get('geo_label')
    o['pic'] = f"https://prod.executori.ro/repes/api/auctions/{e['caseId']}/{e['id']}/pictures/{pics[0]}/thumbnail" if pics else None
    o.update(id=r['id'][:8],mkt_ppm=ppm, mkt_src=src, mkt_value=mv, profit=profit, vs_mkt=vs,
             metro_m=(r['metro'] or {}).get('m') if r.get('metro') else None)
    for k in ('name', 'desc', 'addr'): o[k] = (o[k] or '').replace('⍽', ' ').strip()[:220]
    out.append(o)
y, m, d = RATE_DATE.split('-')
_ty, _tm, _td = TODAY.split('-')
json.dump({'updated': f'{_td}.{_tm}.{_ty}', 'eur': RATE, 'eur_date': f'{d}.{m}.{y}', 'rows': out}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
good = sorted([o for o in out if o['vs_mkt'] and o['kind'] == 'apartament' and 'cota-parte' not in (o['flags'] or '') and 'EXCLUS' not in (o['flags'] or '')], key=lambda o: o['vs_mkt'])
for o in good[:25]:
    print(f"{o['vs_mkt']:>3}% | {o['start_eur']:>7}€ | {o['sqm']}mp {o['rooms']}cam | {o['mkt_ppm']}€/mp {o['mkt_src']} | profit {o['profit']} | {o['city']} {o['county']} | {o['term']} | metro {o['metro_m']} | {o['gps_q'][:10]} | {o['flags']} | {o['name'][:35]}")
