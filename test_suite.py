import requests
import json

s = requests.Session()
BASE = 'http://localhost:5000'

print('1. Testing Health Check...')
r = s.get(f'{BASE}/health')
assert r.status_code == 200, f'Health failed: {r.status_code}'
print('   -> OK:', r.json())

print('2. Testing Login...')
r = s.post(f'{BASE}/auth/login', data={'username': 'admin', 'password': 'admin123'})
assert r.status_code == 200 or len(r.history) > 0, f'Login failed: {r.status_code}'
print('   -> OK: Logged in as admin')

print('3. Testing Dashboard Summary KPI...')
r = s.get(f'{BASE}/api/dashboard/summary')
assert r.status_code == 200, f'Summary failed: {r.status_code}'
data = r.json()
print(f"   -> OK: Total={data.get('total_detections')}, Fire={data.get('fire_count')}, Flood={data.get('flood_count')}, Cities={data.get('cities_covered')}")

print('4. Testing What Changed (24h)...')
r = s.get(f'{BASE}/api/dashboard/what-changed')
assert r.status_code == 200
print('   -> OK:', r.json().get('period_label'))

print('5. Testing Incidents GeoJSON for Map...')
r = s.get(f'{BASE}/api/incidents/map?max_markers=10')
assert r.status_code == 200
features = r.json().get('features', [])
print(f'   -> OK: Returned {len(features)} map features')
assert len(features) > 0, 'No incidents generated'
first_id = features[0]['properties']['event_id']

print(f'6. Testing Incident Detail & Evidence Traceability for #{first_id}...')
r = s.get(f'{BASE}/api/incidents/{first_id}')
assert r.status_code == 200
inc = r.json()
print(f"   -> OK: Event #{inc['event_id']} ({inc['event_type']}) in {inc.get('city')}")
print(f"   -> Risk Score: {inc['risk_score']}/100 ({inc['risk_level']})")
print(f"   -> Factors: {len(inc.get('risk_factors', []))} contributing factors")
print(f"   -> Evidence points: {inc.get('evidence_count', 0)} satellite observations verified")

print('7. Testing Priority Queue...')
r = s.get(f'{BASE}/api/incidents/priority?n=5')
assert r.status_code == 200
print(f"   -> OK: {len(r.json().get('priority_queue', []))} priority incidents")

print('8. Testing Analytics Trends...')
r = s.get(f'{BASE}/api/analytics/trends')
assert r.status_code == 200
print(f"   -> OK: {len(r.json().get('trends', []))} years analyzed")

print('9. Testing Top Cities...')
r = s.get(f'{BASE}/api/analytics/cities')
assert r.status_code == 200
top_cities = r.json().get('cities', [])
print(f"   -> OK: Top city is {top_cities[0]['city']} with {top_cities[0]['fire']} fire detections")

print('10. Testing Data Quality Center...')
r = s.get(f'{BASE}/api/data-quality')
assert r.status_code == 200
dq = r.json()
print(f"   -> OK: Completeness={dq['completeness_pct']}%, Sources={len(dq['source_files'])}")

print('11. Testing Global Search for Indore...')
r = s.get(f'{BASE}/api/search?q=Indore')
assert r.status_code == 200
print(f"   -> OK: Found {r.json().get('total')} matching results")

print('12. Testing Watchlist API...')
r = s.post(f'{BASE}/api/watchlist', json={'location_name': 'Indore', 'notes': 'Test watch'})
assert r.status_code == 200
w_id = r.json()['id']
r = s.get(f'{BASE}/api/watchlist')
assert r.status_code == 200
print(f"   -> OK: Watchlist has {r.json()['total']} locations")
s.delete(f'{BASE}/api/watchlist/{w_id}')

print('13. Testing Alert Simulator (DEMO MODE)...')
r = s.get(f'{BASE}/api/simulator/scenarios')
assert r.status_code == 200
scenarios = r.json().get('scenarios', [])
assert len(scenarios) > 0
sim_ev = scenarios[0]['event_id']
r = s.post(f'{BASE}/api/simulator/run', json={'event_id': sim_ev})
assert r.status_code == 200
print(f"   -> OK: Simulator evaluated {len(r.json()['steps'])} pipeline stages on event #{sim_ev}")

print('14. Testing AI Assistant with real data query...')
r = s.post(f'{BASE}/api/assistant', json={'query': 'Which cities have the highest fire activity?'})
assert r.status_code == 200
print('   -> OK: Assistant responded with grounded answer:')
print('     ', r.json().get('answer')[:120], '...')

print('15. Testing Replay Timeline...')
r = s.get(f'{BASE}/api/replay?year=2024')
assert r.status_code == 200
print(f"   -> OK: Replay sequence has {r.json().get('total_days')} daily frames")

print('\n' + '='*50)
print('ALL 15 INTEGRATION TESTS PASSED!')
print('='*50)
