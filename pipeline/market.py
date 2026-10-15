import json, sys, re, unicodedata, os
from common import HERE
BASE = sys.argv[1]
def n(s): return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()).strip()
# Pret mediu orientativ de piata (EUR/mp util), apartamente in blocuri vechi, toamna 2026. ESTIMARE, de verificat pe imobiliare.ro / storia.ro.
M = {
 'sectorul 1': 2700, 'sectorul 2': 2200, 'sectorul 3': 2100, 'sectorul 4': 1900, 'sectorul 5': 1700, 'sectorul 6': 2000, 'bucuresti': 2100,
 'cluj-napoca': 3200, 'brasov': 2300, 'timisoara': 1800, 'iasi': 1700, 'constanta': 1850, 'sibiu': 1850, 'oradea': 1800,
 'ploiesti': 1350, 'arad': 1350, 'bacau': 1250, 'suceava': 1400, 'galati': 1050, 'braila': 1000, 'pitesti': 1400, 'craiova': 1450,
 'buzau': 1100, 'baia mare': 1200, 'alba iulia': 1450, 'bistrita': 1400, 'zalau': 1150, 'focsani': 1000, 'botosani': 1100,
 'vaslui': 850, 'tulcea': 1000, 'ramnicu valcea': 1150, 'giurgiu': 900, 'calarasi': 850, 'targu mures': 1500, 'deva': 1000,
 'hunedoara': 600, 'petrosani': 500, 'vulcan': 400, 'lupeni': 400, 'petrila': 350, 'medias': 1000, 'turda': 1300,
 'campia turzii': 1100, 'lugoj': 900, 'sfantu gheorghe': 1100, 'mioveni': 1100, 'campulung': 800, 'ramnicu sarat': 700,
 'azuga': 1600, 'bals': 600, 'cugir': 750, 'campeni': 650, 'siret': 600, 'falticeni': 800, 'barlad': 650, 'motru': 350,
 'anina': 250, 'moldova noua': 400, 'copsa mica': 350, 'bicaz': 600, 'targu frumos': 650, 'faurei': 400, 'oltenita': 650,
 'boldesti-scaeni': 900, 'alesd': 800, 'simleu silvaniei': 800, 'chisineu-cris': 700, 'avrig': 900, 'chiajna': 1600,
 'stefanesti': 1300, 'giarmata': 1300, 'vladimirescu': 1300, 'mangalia': 1500, 'navodari': 1500, 'voluntari': 1700,
 'popesti-leordeni': 1500, 'bragadiru': 1400, 'otopeni': 1800, 'pantelimon': 1300, 'roman': 900, 'piatra neamt': 1150,
 'satu mare': 1200, 'resita': 700, 'caransebes': 800, 'slatina': 900, 'targoviste': 1150, 'alexandria': 750, 'slobozia': 800,
 'drobeta-turnu severin': 850, 'targu jiu': 1050, 'miercurea ciuc': 1300, 'odorheiu secuiesc': 1200, 'sighisoara': 1000,
 'fagaras': 1100, 'sacele': 1300, 'codlea': 1100, 'rasnov': 1300, 'onesti': 700, 'moinesti': 600, 'dej': 1000, 'gherla': 900,
 'campina': 1000, 'sinaia': 1900, 'busteni': 1700, 'valenii de munte': 800, 'mizil': 650, 'medgidia': 900, 'tecuci': 650,
 'pascani': 650, 'radauti': 900, 'vatra dornei': 900, 'gura humorului': 900, 'sebes': 1100, 'aiud': 800, 'blaj': 850,
 'orastie': 800, 'brad': 450, 'uricani': 300, 'aninoasa': 300,
}
RURAL = 550
rows = json.load(open(BASE + '/rows.json'))
OV = json.load(open(os.path.join(HERE, 'overrides.json')))
EURX = 5.09
for r in rows:
    o = OV.get(r['id'][:8])
    r['note'] = ''
    if not o: continue
    r['note'] = o.get('note', '')
    if 'term' in o: r['term'] = o['term']
    if 'flags' in o: r['flags'] = o['flags']
    if 'sqm' in o: r['sqm'] = o['sqm']
    if 'rooms' in o: r['rooms'] = o['rooms']
    if r['sqm']: r['eur_m2'] = round(r['start_eur'] / r['sqm'])
    pct = {'I (100%)': 1.0, 'II (75%)': 0.75, 'III (50%)': 0.5}.get(r['term'])
    if 'eval_ron' in o: r['eval'] = o['eval_ron']
    elif pct: r['eval'] = r['start'] / pct
    if r['eval']:
        r['eval_eur'] = round(r['eval'] if r['cur'] == 'EUR' else r['eval'] / EURX)
        r['discount'] = round(100 * (1 - r['start'] / r['eval']))
    if o.get('note', '').startswith('EXCLUS'): r['flags'] = (r['flags'] + ', EXCLUS').strip(', ')
for r in rows:
    c = n(r['city'])
    v = M.get(c)
    r['mkt_src'] = 'oras' if v else 'rural/estimare generica'
    r['mkt_m2'] = v or RURAL
    if r['sqm'] and r['kind'] == 'apartament':
        mv = r['sqm'] * r['mkt_m2']
        reno = max(4000, r['sqm'] * 220)          # renovare cosmetica + mobilare simpla
        costs = r['start_eur'] * 0.02 + mv * 0.05  # intabulare/taxe la cumparare + comision/impozit la vanzare
        r['mkt_value'] = round(mv)
        r['reno'] = round(reno)
        r['profit'] = round(mv - r['start_eur'] - reno - costs)
        r['price_vs_mkt'] = round(100 * r['start_eur'] / mv)
    else:
        r['mkt_value'] = r['reno'] = r['profit'] = r['price_vs_mkt'] = None
json.dump(rows, open(BASE + '/rows2.json', 'w'), ensure_ascii=False)
s = [r for r in rows if r['kind'] == 'apartament' and r['flags'] not in ('cota-parte', 'cota-parte, uzufruct') and 8000 <= r['start_eur'] <= 55000 and r['profit'] is not None]
s.sort(key=lambda r: -r['profit'])
for r in s[:30]:
    print(f"{r['profit']:>7} | {r['price_vs_mkt']:>3}% | {r['start_eur']:>6}€ {r['term']:<10} {r['sqm']:>5}mp {r['mkt_m2']:>5}€/mp ({r['mkt_src'][:5]}) | {r['city'][:18]:<18} {r['county'][:10]:<10} | {r['date'][:10]} | {r['flags']} | {r['name'][:40]}")
print(len(s))
