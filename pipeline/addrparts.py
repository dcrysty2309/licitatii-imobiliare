"""Imparte o adresa romaneasca in componente: tip strada, nume, numar, bloc, scara, etaj, apartament.
Construieste apoi adresa curata pentru harti: "Strada Caminului 22, Sector 2, București"."""
import re, unicodedata

TYPES = [  # (regex, forma completa)
    (r'b-?dul|bd|bld|bdul|bulevardul', 'Bulevardul'), (r'[sș]o?s(?:eaua)?', 'Șoseaua'), (r'calea|cal', 'Calea'),
    (r'aleea|al', 'Aleea'), (r'intrarea|intr', 'Intrarea'), (r'drumul|drum', 'Drumul'), (r'splaiul|spl', 'Splaiul'),
    (r'pia[tț]a|p-?[tț]a', 'Piața'), (r'prelungirea|prel', 'Prelungirea'), (r'fund[aă]tura', 'Fundătura'),
    (r'strada|str', 'Strada'),
]
TYPE_RE = re.compile(r'(?i)(?<![\w-])(' + '|'.join(t for t, _ in TYPES) + r')\b\.?\s*')
NR_RE = re.compile(r'(?i)\b(?:nr|num[aăd]rul|numar)\b\.?\s*:?\s*(\d+(?:\s?[A-Za-z](?![A-Za-z]))?(?:\s?[-–]\s?\d+(?:[A-Za-z](?![A-Za-z]))?)*)')
BL_RE = re.compile(r'(?i)\b(?:bl|bloc|blocul)\b\.?\s*([A-Za-z0-9][A-Za-z0-9\-/]{0,6}(?:\s?\(\d+\))?)')
SC_RE = re.compile(r'(?i)\b(?:sc|se|scara)\b\.?\s*([A-Za-z0-9]{1,3})\b')
ET_RE = re.compile(r'(?i)\b(?:et|etaj|etajul)\b\.?\s*([0-9]{1,2}|[IVX]{1,4}|parter|mansard[aă]|demisol)\b|\b(parter|mansard[aă]|demisol)\b')
AP_RE = re.compile(r'(?i)\b(?:ap|apart|apartament|apartamentul)\b\.?\s*([0-9]{1,4}[A-Za-z]?)\b')
FOSTA = re.compile(r'(?i)\(\s*fost[ae]?\s+(?:str(?:ada)?\.?\s*)?([^)]+)\)')
STOPW = re.compile(r'(?i)^(mun|municipiul|ora[sș]ul|jud|jude[tț]ul|sector|sect|comuna|sat|cod|loc|cartier)\b')

def _n(s): return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()

def _fix_case(name):
    # OCR: "lONITA" -> "IONITA"; apoi Title Case pentru nume scrise cu majuscule
    name = re.sub(r'\bl(?=[A-Z]{2,})', 'I', name)
    if not (name.isupper() or name.islower()):
        small = {'de', 'din', 'la', 'cu', 'si', 'și', 'lui'}
        return ' '.join(w[:1].upper() + w[1:] if w.islower() and (w not in small or i == 0) else w for i, w in enumerate(name.split()))
    if name.isupper() or name.islower():
        small = {'de', 'din', 'la', 'cu', 'si', 'și', 'lui'}
        name = ' '.join(w if w.lower() in small and i else (w[:1].upper() + w[1:].lower()) for i, w in enumerate(name.split()))
    return name

def street_of(text):
    """(tip, nume, nume_vechi) din primul tip de strada gasit."""
    if not text: return None, None, None
    alt = FOSTA.search(text)
    alt = _fix_case(re.sub(r'\s+', ' ', alt.group(1)).strip(' .')) if alt else None
    if alt: alt = TYPE_RE.sub('', alt, count=1).strip() if TYPE_RE.match(alt) else alt
    t = FOSTA.sub('', text)
    for m in TYPE_RE.finditer(t):
        rest = t[m.end():]
        name = re.split(r'(?i),|;|\(|\bnr\b|\bnum[aăd]rul\b|\bbl\b|\bbloc|\bsc\b|\bet\b|\bap\b|\bjud', rest)[0]
        name = re.sub(r'\s+', ' ', name).strip(' .-–')
        if not name or STOPW.match(name) or len(name) < 2: continue
        kind = next(full for rx, full in TYPES if re.fullmatch(rx, m.group(1), re.I))
        # "Strada Drumul Malu Mierii" -> tipul real e cel din nume
        m2 = re.match(r'(?i)^(drumul|calea|aleea|al|intrarea|intr|bulevardul|b-dul|bd|[sș]oseaua|[sș]os|splaiul|prelungirea|fund[aă]tura)\.?\s+(.+)$', name)
        if m2:
            kind = next(full for rx, full in TYPES if re.fullmatch(rx, m2.group(1), re.I)); name = m2.group(2)
        return kind, _fix_case(name), alt
    return None, None, alt

def components(pub, repes):
    """Combina adresa din publicatie (prioritara) cu cea din REPES."""
    out = {}
    for src in (pub, repes):
        if not src: continue
        src = re.sub(r'\s+', ' ', src)
        if 'street' not in out:
            kind, name, alt = street_of(src)
            if name:
                out['type'], out['street'] = kind, name
                if alt: out['street_alt'] = alt
                # numar lipit de nume: "Aleea Sălaj 21"
                m = re.match(r'^(.*?[A-Za-zĂÂÎȘŞȚŢăâîșşțţ.])\s+(\d+[A-Za-z]?(?:[-–]\d+[A-Za-z]?)?)$', name)
                if m and not re.match(r'^\d', name):
                    out['street'] = m.group(1)
                    out.setdefault('nr', m.group(2).replace('–', '-'))
        for key, rx in (('nr', NR_RE), ('bl', BL_RE), ('sc', SC_RE), ('ap', AP_RE)):
            if key not in out:
                m = rx.search(src)
                if m: out[key] = m.group(1).replace(' ', '').replace('–', '-')
        if 'et' not in out:
            m = ET_RE.search(src)
            if m:
                v = m.group(1) or m.group(2)
                out['et'] = v.upper() if re.fullmatch(r'(?i)[IVX]+', v) else v.lower().replace('mansarda', 'mansardă')
    return out

def place(city, county):
    m = re.match(r'(?i)sectorul\s*(\d)', city or '')
    if m: return f'Sector {m.group(1)}, București'
    if _n(city) == 'bucuresti': return 'București'
    return city or ''

def maps_address(c, city, county, use_alt=False):
    street = c.get('street_alt') if use_alt and c.get('street_alt') else c.get('street')
    if not street:
        return f"{place(city, county)}, județul {county}" if county and _n(county) not in _n(city) and 'Bucure' not in place(city, county) else place(city, county)
    s = f"{c.get('type', 'Strada')} {street}"
    if c.get('nr'): s += f" {c['nr']}"
    return f"{s}, {place(city, county)}"
