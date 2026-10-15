import json, os, re, sys, unicodedata
from common import TODAY
from addrx import extract as extract_addr
import json as _json
from common import HERE as _HERE
ADDR_MANUAL = _json.load(open(os.path.join(_HERE, 'addr_manual.json')))
BASE = sys.argv[1]
EUR = 5.09
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return s
NUM = re.compile(r'(?<![\d.,])(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d{4,9}(?:[.,]\d{1,2})?)(?![\d])')
def to_float(t):
    t = t.strip().replace(' ', '')
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', t): t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?', t): t = t.replace(',', '')
    else: t = t.replace(',', '.')
    try: return float(t)
    except: return None
def amounts(text):
    out = []
    for m in NUM.finditer(text):
        v = to_float(m.group(1))
        if v and 3000 <= v <= 50_000_000: out.append((v, m.start()))
    return out
def classify(start, text):
    am = amounts(text)
    best = None
    for ratio, label in ((0.5, 'III (50%)'), (0.75, 'II (75%)'), (1.0, 'I (100%)')):
        target = start / ratio
        for v, pos in am:
            if abs(v - target) / target < 0.006:
                if ratio == 1.0:
                    best = best or (v, label)
                else:
                    return v, label
    # explicit statement right after the start price, e.g. "reprezentand 75% din pretul de evaluare"
    m = re.search(r'(reprez\w*|adica|respectiv|redus\s*cu)[\s,]*(100|75|50)\s*[%9]\s*din\s*(pretul|valoarea)\s*(de\s*evaluare|la\s*care|fixat|de\s*pornire\s*a\w*\s*prime\w*)', text)
    if m:
        pct = int(m.group(2))
        label = {100: 'I (100%)', 75: 'II (75%)', 50: 'III (50%)'}[pct]
        return start / (pct / 100), label
    if best:
        return best
    return None, 'neclar'
def sqm(e, text):
    ok = lambda v: v is not None and 14 <= v <= 160
    src = norm((e['asset'].get('description') or '') + ' ' + (e['asset'].get('name') or '')) + ' ' + text
    m = re.search(r'(suprafata\s*utila|s\.?\s*u\.?|utila)\s*(de|totala|=|:)?\s*(de)?\s*(\d{2,3}(?:[.,]\d{1,2})?)\s*(mp|m2|m\.p|m\s*p)', src)
    if m:
        v = float(m.group(4).replace(',', '.'))
        if ok(v): return v
    for p in e['asset'].get('properties') or []:
        if p['propertyType'] == 'USU' and p.get('value'):
            try:
                v = float(p['value'].replace(',', '.'))
                if ok(v): return v
            except: pass
    return None
def rooms(e, text):
    for p in e['asset'].get('properties') or []:
        if p['propertyType'] == 'ROM':
            try: return int(float(p['value']))
            except: pass
    src = norm((e['asset'].get('name') or '') + ' ' + (e['asset'].get('description') or ''))
    m = re.search(r'(\d)\s*(camere|camera|cam\.)', src)
    if m: return int(m.group(1))
    if re.search(r'o\s*camera|garsonier', src): return 1
    return None
def kind(e):
    nm = norm(e['asset'].get('name') or '')
    if re.search(r'\bcas[ae]\b|teren|constructi|spatii|spatiu|cote\b', nm) and not re.search(r'apartament|garsonier', nm):
        if re.search(r'\bcas[ae]\b|constructi', nm): return 'casa'
        if re.search(r'spatii|spatiu', nm): return 'spatiu comercial'
        if re.search(r'cote\b', nm): return 'cote'
        return 'teren'
    s = nm + ' ' + norm(e['asset'].get('description') or '')
    if re.search(r'bmw|autoturism|motociclu|stoc bunuri|autovehicul', s): return 'altceva'
    if re.search(r'camin', s): return 'camera camin'
    if re.search(r'ap[ar]{1,2}t?[ae]?m[ae]n[te]{1,2}|apartmanet|garsonier|\bap\.|\bapt\b|\d\s*camer[ae]|o\s*camera|una\s*camera', s): return 'apartament'
    if re.search(r'\bcas[ae]\b|locuint|constructi', s): return 'casa'
    if re.search(r'teren|faneata|parcare', s): return 'teren'
    return 'neclar'
def flags(e, text, s_eur):
    s = norm((e['asset'].get('name') or '') + ' ' + (e['asset'].get('description') or ''))
    f = []
    nm = norm(e['asset'].get('name') or '')
    def cota_of_property(src):
        found = []
        for m in re.finditer(r'\bcot[ae]\s*-?\s*(parte\s*)?(indiviz[ae]\s*)?(de\s*)?(\d+)\s*/\s*(\d+)(?=(.{0,40}))', src):
            a, b, tail = m.group(4), m.group(5), m.group(6)
            before = src[max(0, m.start() - 30):m.start()]
            if a == b: continue
            if re.match(r'\s*(parte\s*)?(din|asupra)\s*(dreptul[^.]{0,30})?(apartament|imobil|locuint|cas[ae]\b|garsonier)', tail):
                found.append((a, b)); continue
            if re.search(r'part|teren|comun|folosin|\buz\b|mp|p\.c\.i', tail[:30]) or re.search(r'teren\w*|comun\w*|parti\w*', before): continue
            found.append((a, b))
        # co-owners each holding 1/2 (or 1/3...) of the same flat => the whole flat is sold
        for a, b in set(found):
            if a == '1' and found.count((a, b)) >= int(b) and found.count((a, b)) % int(b) == 0: found = [x for x in found if x != (a, b)]
        if found: return True
        for m in re.finditer(r'(\d+)\s*/\s*(\d+)\s*(din|asupra)\s*(dreptul\s*de\s*proprietate\s*asupra\s*)?(apartament|imobil|locuint|cas[ae]\b|garsonier)', src):
            if m.group(1) != m.group(2): return True
        return False
    if nm.startswith('cota') or cota_of_property(nm) or cota_of_property(s):
        f.append('cota-parte')
    elif s_eur < 4000 or cota_of_property(text[:4000]):
        f.append('cota-parte? (verifica)')
    if re.search(r'uzufruct|nud[ae]\s*proprietat', s) or re.search(r'(dreptul?\s*de\s*uzufruct\s*(viager\s*)?(in\s*favoarea|al\s*numit|constituit))|grevat\w*\s*de\s*(un\s*)?(drept\s*de\s*)?uzufruct', text):
        f.append('uzufruct')
    if re.search(r'drept\w*\s*de\s*abitati\w*\s*(viager\w*\s*)?(in\s*favoarea|constituit)', text): f.append('drept abitatie')
    if re.search(r'contract\w*\s*de\s*(inchiriere|locatiune)', text): f.append('chirias?')
    if re.search(r'litigi', text): f.append('litigiu?')
    if re.search(r'(se\s*(va\s*)?adauga\w*\s*(si\s*)?(cota\s*de\s*)?tva|plus\s*tva|\+\s*tva|exclusiv\s*tva|nu\s*include\w*\s*tva)', text): f.append('+TVA')
    if re.search(r'decedat', text): f.append('debitor decedat')
    return ', '.join(f)
rows = []
for e in json.load(open(os.path.join(BASE, 'apts_all.json'))):
    if e['date'][:10] < TODAY: continue
    tp = os.path.join(BASE, 'txt', e['id'] + '.txt')
    raw = open(tp, encoding='utf-8', errors='ignore').read() if os.path.exists(tp) else ''
    text = norm(raw)
    p = e['asset']['price']
    start = p['value'] or 0
    cur = p['currency']
    ev, term = classify(start, text) if start and text else (None, 'fara text' if not text else 'neclar')
    s_eur = start if cur == 'EUR' else start / EUR
    ev_eur = None if ev is None else (ev if cur == 'EUR' else ev / EUR)
    a = e['asset']['address']
    m2 = sqm(e, text)
    rows.append(dict(
        id=e['id'], caseId=e['caseId'], date=e['date'][:16].replace('T', ' '),
        county=a.get('county') or '', city=a.get('city') or '', addr=a.get('originalAddress') or '',
        name=e['asset'].get('name') or '', desc=e['asset'].get('description') or '',
        rooms=rooms(e, text), sqm=m2, cur=cur, start=start, start_eur=round(s_eur),
        eval=ev, eval_eur=None if ev_eur is None else round(ev_eur), term=term,
        discount=None if ev is None else round(100 * (1 - start / ev)),
        eur_m2=None if not m2 else round(s_eur / m2),
        link=f"https://prod.executori.ro/repes/listing/{e['caseId']}/{e['id']}",
        pdf=f"https://prod.executori.ro/repes/api/auctions/{e['caseId']}/{e['id']}/publication/",
        addr_pub=ADDR_MANUAL.get(e['id'][:8]) or (extract_addr(raw) if raw else None),
        kind=kind(e), flags=flags(e, text, s_eur), textlen=len(text)))
json.dump(rows, open(os.path.join(BASE, 'rows.json'), 'w'), ensure_ascii=False, indent=0)
from collections import Counter
print(len(rows), Counter(r['term'] for r in rows))
print('with sqm', sum(1 for r in rows if r['sqm']))
