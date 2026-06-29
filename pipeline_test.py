import sys, os
sys.path.insert(0, 'ig_outreach')
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('forge_system/.env'))

import ig_client, target_finder, db
from google import genai

db.init_db()
cl = ig_client.build_client()
cl = ig_client.login(cl)
gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY_DEVAN'))

print('Searching: realtor india ...')
uids = ig_client.search_users_by_keyword(cl, 'realtor india', limit=15)
print(f'Found {len(uids)} users\n')

for uid in uids[:5]:
    try:
        info = cl.user_info(int(uid))
        f    = info.follower_count or 0
        bio  = (info.biography or '')[:60]
        print(f'@{info.username} | {f} followers | {bio}')
        if 500 <= f <= 2000:
            v = target_finder.validate_account(
                gemini, info.username, info.full_name or '',
                info.biography or '', f, info.following_count or 0,
                bool(info.is_business), bool(info.external_url)
            )
            print(f'  -> valid={v["is_valid"]} type={v["business_type"]} conf={v["confidence"]}%')
        else:
            print(f'  -> skipped ({f} followers out of 500-2k range)')
    except Exception as e:
        print(f'  error uid {uid}: {e}')
