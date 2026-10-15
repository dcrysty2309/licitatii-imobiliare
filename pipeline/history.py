"""Pasul final: istoricul fiecarei licitatii.

Compara lista de azi (data.json) cu history.json de ieri si noteaza:
  nou        - a aparut pe REPES
  pret       - s-a schimbat pretul de pornire
  termen     - s-a schimbat termenul (I -> II -> III)
  data       - s-a mutat data licitatiei
  iesit      - nu mai apare (licitatie trecuta sau retrasa de executor)
Apoi pune in data.json: first_seen, events pentru fiecare licitatie activa
si lista 'removed' cu licitatiile iesite in ultimele 90 de zile.
"""
import json, os, sys
from datetime import date, timedelta
from common import TODAY

DATA, HIST = sys.argv[1], sys.argv[2]
data = json.load(open(DATA))
hist = json.load(open(HIST)) if os.path.exists(HIST) else {}

SNAP = ('city', 'county', 'name', 'rooms', 'sqm', 'start_eur', 'term', 'date', 'link', 'pdf', 'kind', 'flags', 'vs_mkt', 'mkt_ppm', 'eur_m2')
today_ids = set()
for r in data['rows']:
    rid = r['id']; today_ids.add(rid)
    snap = {k: r.get(k) for k in SNAP}
    h = hist.get(rid)
    if h is None:
        hist[rid] = h = {'first_seen': TODAY, 'last_seen': TODAY, 'status': 'activ', 'events': [{'d': TODAY, 't': 'nou', 'v': r.get('start_eur')}], 'snap': snap}
    else:
        old = h.get('snap') or {}
        if old.get('start_eur') and r.get('start_eur') and abs(old['start_eur'] - r['start_eur']) >= 50:
            h['events'].append({'d': TODAY, 't': 'pret', 'from': old['start_eur'], 'to': r['start_eur']})
        if old.get('term') and r.get('term') and old['term'] != r['term']:
            h['events'].append({'d': TODAY, 't': 'termen', 'from': old['term'], 'to': r['term']})
        if old.get('date') and r.get('date') and old['date'][:10] != r['date'][:10]:
            h['events'].append({'d': TODAY, 't': 'data', 'from': old['date'][:10], 'to': r['date'][:10]})
        if h.get('status') != 'activ':
            h['events'].append({'d': TODAY, 't': 'revenit'})
        h.update(last_seen=TODAY, status='activ', snap=snap)

for rid, h in hist.items():
    if rid in today_ids or h.get('status') != 'activ': continue
    when = (h.get('snap') or {}).get('date', '')[:10]
    reason = 'licitatie trecuta' if when and when < TODAY else 'retrasa din REPES'
    h.update(status=reason, removed_on=TODAY)
    h['events'].append({'d': TODAY, 't': 'iesit', 'v': reason})

json.dump(hist, open(HIST, 'w'), ensure_ascii=False, separators=(',', ':'))

cutoff = (date.fromisoformat(TODAY) - timedelta(days=90)).isoformat()
for r in data['rows']:
    h = hist[r['id']]
    r['first_seen'] = h['first_seen']
    r['events'] = h['events'][-12:]
data['removed'] = sorted([dict(h['snap'], id=rid, status=h['status'], removed_on=h['removed_on'], first_seen=h['first_seen'])
                          for rid, h in hist.items() if h.get('status') != 'activ' and h.get('removed_on', '') >= cutoff],
                         key=lambda x: x['removed_on'], reverse=True)
data['tracked_since'] = min((h['first_seen'] for h in hist.values()), default=TODAY)
json.dump(data, open(DATA, 'w'), ensure_ascii=False, separators=(',', ':'))
new_today = sum(1 for h in hist.values() if h['first_seen'] == TODAY)
print(f'istoric: {len(hist)} urmarite, {len(today_ids)} active, {new_today} noi azi, {len(data["removed"])} iesite in ultimele 90 de zile')
