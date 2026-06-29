import sys, os
sys.path.insert(0, r'C:\Users\Marilyn\Downloads\AI OS\ig_outreach')
from dotenv import load_dotenv; from pathlib import Path
load_dotenv(Path(r'C:\Users\Marilyn\Downloads\AI OS\forge_system\.env'))
import httpx

URL = os.getenv('SUPABASE_URL', '').rstrip('/')
KEY = os.getenv('SUPABASE_SERVICE_KEY', '')
h = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

r = httpx.get(f'{URL}/rest/v1/ig_outreach', headers=h,
              params={'select': 'username,business_type,followers,region,dm_sent_at',
                      'order': 'dm_sent_at.desc', 'limit': '20'})
data = r.json()
if isinstance(data, list):
    print(f'DMs sent so far: {len(data)}')
    for row in data:
        print(f'  @{row["username"]} | {row["business_type"]} | {row["followers"]} followers | {row["region"]} | {str(row["dm_sent_at"])[:16]}')
else:
    print('Response:', data)
