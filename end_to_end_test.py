"""
Full end-to-end test: login → search → validate → send one real DM.
Writes everything to end_to_end.log
"""
import sys, os
sys.path.insert(0, 'ig_outreach')
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('forge_system/.env'))

import ig_client, target_finder, db, dm_engine
from google import genai

log_path = Path('end_to_end.log')

def log(msg):
    print(msg)
    with open(log_path, 'a') as f:
        f.write(msg + '\n')

log('=== END TO END TEST ===')

# Init
db.init_db()
log(f'DB: OK (supabase={db._USE_SUPABASE})')

# Login
cl = ig_client.build_client()
cl = ig_client.login(cl)
log(f'Login: OK — @{cl.username}')

# Gemini
gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY_DEVAN'))
log('Gemini: OK')

# Search
keyword = 'realtor india'
log(f'\nSearching: {keyword}')
uids = ig_client.search_users_by_keyword(cl, keyword, limit=20)
log(f'Found {len(uids)} user IDs')

# Try to find one valid target and send a DM
sent = False
for uid in uids:
    if db.has_been_messaged(uid):
        log(f'  uid {uid}: already messaged, skip')
        continue

    info = ig_client.get_user_info_by_id(cl, int(uid))
    if not info:
        log(f'  uid {uid}: could not fetch profile')
        continue

    username  = info.username
    full_name = info.full_name or ''
    bio       = info.biography or ''
    followers = info.follower_count or 0
    has_web   = bool(info.external_url)

    log(f'  @{username} | {followers} followers | bio: {bio[:60]}')

    if followers < 500 or followers > 2000:
        log(f'    -> skip ({followers} followers out of range)')
        continue

    if not bio and not full_name:
        log('    -> skip (no bio or name)')
        continue

    # Validate
    v = target_finder.validate_account(gemini, username, full_name, bio,
                                       followers, info.following_count or 0,
                                       bool(info.is_business), has_web)
    log(f'    Gemini: valid={v["is_valid"]} type={v["business_type"]} conf={v["confidence"]}%')

    if not v.get('is_valid') or v.get('confidence', 0) < 65:
        log(f'    -> skip ({v.get("reason","")})')
        continue

    biz_type = v['business_type']
    message  = dm_engine.generate_dm(gemini, username, biz_type, bio, has_web)
    log(f'    Message: {message}')

    # Send
    ok = ig_client.send_dm(cl, uid, message)
    log(f'    Send result: {"SUCCESS" if ok else "FAILED"}')

    if ok:
        db.mark_as_messaged(uid, username, full_name, biz_type,
                            'india', followers, has_web, message)
        log(f'    Logged to DB')
        sent = True
        break

log(f'\nResult: {"1 DM sent" if sent else "No DM sent — no valid targets found in this batch"}')
