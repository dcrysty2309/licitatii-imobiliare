"""Extrage adresa exacta a imobilului din textul publicatiei (OCR)."""
import re
ABBR = {'str', 'nr', 'bl', 'sc', 'et', 'ap', 'mun', 'jud', 'loc', 'com', 'sat', 'bd', 'b-dul', 'bdul', 'sos', 'şos', 'șos', 'cam',
        'int', 'intr', 'al', 'sect', 'or', 'oras', 'prel', 'cart', 'tarla', 'parc', 'sp', 'nr.cad', 'cf', 'p-ta', 'pta', 'spl', 'cal', 'dr'}
ANCH = re.compile(r'(?:s\w?ituat[aăe]?\s*(?:[îiIl1T]n|irr?|ip|la)\s*:?|cu\s+adresa\s*(?:[îi]n|la)?\s*:?|adresa\s*(?:imobilului)?\s*(?::|(?=(?:str|strada|bd|b-dul|calea|aleea|[sș]os|drumul|mun|ora[sș]ul|comuna|sat)\b))|imobil(?:ul)?\s+(?:din|de\s+la)\s)', re.I)
STOP = re.compile(r'(?:,?\s*(?:jud(?:e[tţț]ul)?\.?|jude[tţț]ul)\s+[A-ZĂÂÎȘŞȚŢ]|,?\s*[îi]nscris|,?\s*identificat|,?\s*av[aâ]nd\s+(?:nr|num|cf|suprafa)|,?\s*compus|,?\s*cu\s+suprafa|,?\s*[îi]n\s+suprafa|,?\s*CF\s*(?:nr)?|,?\s*carte(?:a)?\s+funciar|,?\s*proprietatea|,?\s*apar[tţț]in|,?\s*evaluat|,?\s*la\s+pre[tţț]ul|,?\s*nr\.?\s*cadastral|\(\s*cod\s+interfon|,?\s*cod\s+po[sș]tal|\(prin|,?\s*a[sș]a\s+cum|,?\s*edificat|;\s*proprietar|;\s*sarcin|,?\s*UAT\b|;\s*nr\.?\s*cadastral|,?\s*Rom\S{0,3}nia\b|,?\s*cu\s+o\s+suprafa)', re.I)
GOOD = re.compile(r'(?i)\b(str|strada|bd|b-dul|bulevardul|calea|aleea|al|sos|șos|şos|soseaua|intrarea|piata|p-ta|splaiul|drumul)\b')
BAD_CTX = re.compile(r'(?i)(domicili|cu\s+sediul|sediul|biroul|cabinet|executor|cu\s+re[sș]edin|coresponden|creditor|locul\s+licita|licita[tţț]i[ae]\s+(?:se\s+)?(?:va|are)|s\.?r\.?l|s\.a\.|ifn|cif\b)')

def _cut_sentence(s):
    for m in re.finditer(r'\.\s+(?=[A-ZĂÂÎȘŞȚŢ])', s):
        prev = re.findall(r'([\w\-\.]+)$', s[:m.start()])
        w = (prev[0] if prev else '').lower().strip('.')
        last = w.split('.')[-1]
        if last in ABBR or len(last) <= 2: continue
        return s[:m.start()]
    return s

def clean(s):
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r"(?<=\w)['’`](?=\s*\w)", '. ', s)              # OCR: str'Mihai -> str. Mihai
    s = re.sub(r'(?i)\b(nr|bl|sc|et|ap|str|mun|jud)\s*[,;]\s*(?=\w)', lambda m: m.group(1) + '. ', s)  # ap,69 -> ap. 69
    s = re.sub(r'\.(?=[A-Za-zĂÂÎȘŞȚŢăâîșşțţ])', '. ', s)
    s = re.sub(r'\s*—\s*', ', ', s)
    s = re.sub(r'\s+([,.])', r'\1', s)
    return s.strip(' ,;:-–')

def extract(text):
    best = None
    for m in ANCH.finditer(text):
        ctx = text[max(0, m.start() - 70):m.start()]
        if BAD_CTX.search(ctx): continue
        seg = text[m.end():m.end() + 320]
        st = STOP.search(seg)
        if st: seg = seg[:st.start()]
        seg = clean(_cut_sentence(seg))
        if len(seg) < 8 or not GOOD.search(seg): continue
        if BAD_CTX.search(seg): continue
        score = len(re.findall(r'(?i)\b(nr|num[aă]rul|bl|blocul|sc|scara|et|etajul|ap|apartamentul|str|strada)\b', seg))
        if best is None or score > best[0]: best = (score, seg[:220])
        if score >= 4: break
    return best[1] if best else None
