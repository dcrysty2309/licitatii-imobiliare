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
WORDS = r'(?:reprez\w*|adica|adică|respectiv|ce\s+reprezint\w*|care\s+reprezint\w*)'
def _fmt_variants(v):
    out = set()
    for i in {int(v), int(round(v))}:
        s = f"{i:,}".replace(',', '.'); out |= {s, s.replace('.', ' '), str(i), s.replace('.', ',')}
    return out
def _positions(start, text):
    pos = []
    for f in _fmt_variants(start):
        for m in re.finditer(re.escape(f) + r'(?![\d])', text): pos.append(m.start())
    return sorted(set(pos))
def _amounts_near(text, a, b):
    seg = text[a:b]; out = []
    for m in re.finditer(r'(?<![\d.,])(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d{4,9}(?:[.,]\d{1,2})?)(?!\d)', seg):
        t = m.group(1).replace(' ', '')
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', t): t = t.replace('.', '').replace(',', '.')
        else: t = t.replace(',', '.')
        try: out.append((float(t), a + m.start()))
        except: pass
    return out
LBL = {100: 'I (100%)', 75: 'II (75%)', 50: 'III (50%)'}
def _label(pct):
    for k in (100, 75, 50):
        if abs(pct - k) <= 2: return LBL[k]
    return f'{round(pct)}%'
def classify(start, text):
    """-> (evaluare, eticheta, dovada). Bazat pe ce scrie explicit in publicatie."""
    pos = _positions(start, text)
    windows = [(max(0, p - 350), p + 450) for p in pos] or []
    def snippet(m, base=0):
        a = max(0, base + m.start() - 90); b = base + m.end() + 60
        return re.sub(r'\s+', ' ', text[a:b]).strip()
    # 1) procent explicit langa pretul de pornire
    for a, b in windows:
        seg = text[a:b]
        m = re.search(WORDS + r'[\s,:]*(\d{2,3})(?:[.,]0+)?\s*[%9][^%]{0,45}?din\s*(?:pretul|valoarea|pre[tț]ul)\s*(?:de\s*evaluare|la\s*care|fixat|stabilit|de\s*pornire\s*a\w*\s*prime\w*|ini[tț]ial)', seg)
        if m and 30 <= int(m.group(1)) <= 100:
            pct = int(m.group(1)); return start / (pct / 100), _label(pct), snippet(m, a)
        m = re.search(r'(?:redus\w*|sc[aă]zut\w*|diminuat\w*|reducere\w*)\s*(?:cu|de)\s*(25|50)\s*%', seg)
        if m:
            pct = 100 - int(m.group(1)); return start / (pct / 100), _label(pct), snippet(m, a)
        m = re.search(r'(?:pre[tț]\w*\s*)?(?:determinat|stabilit)\s*prin\s*evaluare|reprezint\w*\s*(?:100\s*%|integral)|egal\w*\s*cu\s*pre[tț]ul\s*de\s*evaluare|pre[tț]ul\s*de\s*evaluare\s*(?:al\s*imobilului\s*)?(?:este\s*)?(?:si\s*)?pre[tț]ul\s*de\s*pornire', seg)
        if m: return start, LBL[100], snippet(m, a)
    # 2) valoare de evaluare scrisa explicit
    for m in re.finditer(r'(?:evaluat\w*\s*(?:la\s*(?:suma\s*de\s*)?|in\s*cuantum\s*de\s*)|pre[tț]ul\s*de\s*evaluare\s*(?:este\s*(?:de\s*)?|de\s*|in\s*cuantum\s*de\s*)?|valoarea\s*(?:de\s*evaluare|stabilit[aă]\s*prin\s*raport\w*)\s*(?:este\s*(?:de\s*)?|de\s*)?)', text):
        for v, p in _amounts_near(text, m.end(), m.end() + 40)[:1]:
            if v >= start * 0.98 and v <= start * 2.2:
                pct = 100 * start / v
                if 45 <= pct <= 101: return v, _label(pct), snippet(m)
    # 3) termen numit explicit langa pret ("pentru termen III", "a doua licitatie")
    for a, b in windows:
        seg = text[a:b]
        m = re.search(r'(?:pentru\s*)?termen(?:ul)?\s*(?:nr\.?\s*)?(iii|ii|i)\b(?!\s*(?:alin|lit))', seg)
        if m:
            pct = {'i': 100, 'ii': 75, 'iii': 50}[m.group(1)]; return start / (pct / 100), _label(pct), snippet(m, a)
    return None, 'neclar', None

BOILER = re.compile(r'(?:de\s*la\s*pre[tț]ul\s*de|va\s*(?:incepe|începe)|nu\s*mai\s*pu[tț]in\s*de|in\s*cazul\s*in\s*care|daca\s*nu|la\s*acest\s*termen|la\s*urm[aă]torul\s*termen)', re.I)
def _not_boiler(text, m, start=None):
    before = text[max(0, m.start() - 80):m.start()]
    if start and any(f in before for f in _fmt_variants(start)): return True   # fraza contine chiar pretul de pornire
    return not BOILER.search(before[-45:])
_classify_window = classify
def classify(start, text):
    ev, lab, sn = _classify_window(start, text)
    if lab != 'neclar': return ev, lab, sn
    def snippet(m):
        return re.sub(r'\s+', ' ', text[max(0, m.start() - 90):m.end() + 60]).strip()
    # procent explicit oriunde, in afara formulelor standard din lege
    for m in re.finditer(WORDS + r'[\s,:]*(\d{2,3})(?:[.,]00)?\s*[%9][^%]{0,45}?din\s*(?:pretul|valoarea|pre[tț]ul)\s*(?:de\s*evaluare|la\s*care|fixat|stabilit|de\s*pornire\s*a\w*\s*prime\w*|ini[tț]ial|evaluat)', text):
        if _not_boiler(text, m, start) and 45 <= int(m.group(1)) <= 100:
            pct = int(m.group(1)); return start / (pct / 100), _label(pct), snippet(m)
    for m in re.finditer(r'(?:pre[tț]\w*[^.]{0,80}?)(?:redus\w*|sc[aă]zut\w*|diminuat\w*)\s*cu\s*(25|50)\s*%', text):
        if _not_boiler(text, m, start):
            pct = 100 - int(m.group(1)); return start / (pct / 100), _label(pct), snippet(m)
    for m in re.finditer(r'pentru\s*termen(?:ul)?\s*(iii|ii|i)\b[^.]{0,60}?(?:reprezint|este)', text):
        pct = {'i': 100, 'ii': 75, 'iii': 50}[m.group(1)]; return start / (pct / 100), _label(pct), snippet(m)
    m = re.search(r'pre[tț]\w*\s*(?:de\s*pornire|de\s*incepere)[^.]{0,120}?(?:determinat|stabilit)\s*prin\s*(?:evaluare|raport\w*\s*de\s*evaluare|expertiz)', text)
    if m: return start, LBL[100], snippet(m)
    m = re.search(r'reprezent\w*\s*pre[tț]ul\s*la\s*care\s*a\s*fost\s*eva', text)
    if m: return start, LBL[100], snippet(m)
    m = re.search(r'pentru\s*termen(?:ul)?\s*[|l1]\s*(?:este|reprezint)', text)
    if m: return start, LBL[100], snippet(m)
    # valoarea evaluata scrisa altfel: "pretul la care a fost evaluat imobilul este de X", "stabilit la valoarea de X"
    for m in re.finditer(r'(?:evaluat\w*\s*(?:imobilul\w*\s*)?este\s*de|stabilit\s*la\s*valoarea\s*de|evaluat\w*\s*la\s*valoarea\s*de)', text):
        for v, p in _amounts_near(text, m.end(), m.end() + 30)[:1]:
            if start * 0.98 <= v <= start * 2.2:
                pct = 100 * start / v
                if 45 <= pct <= 101: return v, _label(pct), snippet(m)
    return None, 'neclar', None

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
    ev, term, term_src = classify(start, text) if start and text else (None, 'fara text' if not text else 'neclar', None)
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
        term_src=term_src,
        addr_pub=ADDR_MANUAL.get(e['id'][:8]) or (extract_addr(raw) if raw else None),
        kind=kind(e), flags=flags(e, text, s_eur), textlen=len(text)))
json.dump(rows, open(os.path.join(BASE, 'rows.json'), 'w'), ensure_ascii=False, indent=0)
from collections import Counter
print(len(rows), Counter(r['term'] for r in rows))
print('with sqm', sum(1 for r in rows if r['sqm']))
