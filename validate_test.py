import sys
sys.path.insert(0, r'C:\Users\Marilyn\Downloads\AI OS\ig_outreach')
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(r'C:\Users\Marilyn\Downloads\AI OS\forge_system\.env'))
import os
from google import genai
import target_finder

# Use a non-rate-limited key
key = os.getenv('GEMINI_API_KEY_DEVAN') or os.getenv('GEMINI_API_KEY_AKHIL') or os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=key)
print(f"Using key: ...{key[-8:]}")

test_accounts = [
    dict(username='luxemedspa_houston',   name='Luxe Med Spa Houston',      bio='Botox | Fillers | Skin Treatments | Book now',                              followers=1200, following=800,  biz=True,  web=True),
    dict(username='johnhvacservices',     name='John HVAC Services',         bio='AC repair and installation. Serving Dallas TX. Call us!',                   followers=340,  following=290,  biz=True,  web=False),
    dict(username='travel_vibes2024',     name='Travel Vibes',               bio='Just vibes and adventures around the world',                                followers=5000, following=4000, biz=False, web=False),
    dict(username='smithdentalclinic',    name='Smith Dental Clinic',        bio='Family dentistry. New patients welcome. Mon-Sat 8am-6pm',                   followers=890,  following=450,  biz=True,  web=True),
    dict(username='digitaledgeagency',    name='Digital Edge Marketing',     bio='We help small businesses grow online. Google Ads | SEO | Meta',             followers=2100, following=1800, biz=True,  web=True),
    dict(username='the_real_kardashian',  name='Kim K Fan Page',             bio='Fan account for the Kardashians. Not official.',                            followers=45000,following=200,  biz=False, web=False),
    dict(username='eliteroofing_atl',     name='Elite Roofing Atlanta',      bio='Expert roofing services in Atlanta GA. Free estimates. 20yr warranty.',     followers=560,  following=430,  biz=True,  web=True),
    dict(username='yogastudio_miami',     name='Zen Flow Yoga',              bio='Hot yoga | Pilates | Meditation. Classes 7 days a week. Book online.',      followers=3200, following=1100, biz=True,  web=True),
]

print('Validating accounts...')
print('=' * 65)
valid = 0
for acc in test_accounts:
    result = target_finder.validate_account(
        client, acc['username'], acc['name'], acc['bio'],
        acc['followers'], acc['following'], acc['biz'], acc['web']
    )
    is_valid = result.get('is_valid', False)
    status   = 'TARGET' if is_valid else 'SKIP  '
    conf     = result.get('confidence', 0)
    btype    = result.get('business_type') or 'N/A'
    reason   = result.get('reason', '')
    if is_valid:
        valid += 1
    print(f'[{status}] @{acc["username"]:<30} {btype:<25} {conf}%  {reason[:50]}')

print('=' * 65)
print(f'Valid targets: {valid}/{len(test_accounts)}')
