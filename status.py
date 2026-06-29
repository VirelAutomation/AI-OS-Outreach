import sqlite3, os

DB = r'C:\Users\Marilyn\Downloads\AI OS\ig_outreach\outreach.db'
if not os.path.exists(DB):
    print("DB not created yet"); exit()

conn = sqlite3.connect(DB)

print("=== DMs SENT ===")
rows = conn.execute(
    "SELECT id,username,business_type,followers,region,message_sent,dm_sent_at FROM ig_outreach ORDER BY dm_sent_at DESC"
).fetchall()
print(f"Total: {len(rows)}")
for r in rows:
    print(f"  @{r[1]} | {r[2]} | {r[3]} followers | {r[4]} | {str(r[6])[:16]}")
    print(f"    MSG: {r[5][:110]}")

print()
print("=== FOLLOW-UPS SCHEDULED ===")
frows = conn.execute(
    "SELECT id,username,followup_number,scheduled_for,status FROM ig_followups ORDER BY scheduled_for"
).fetchall()
print(f"Total: {len(frows)}")
for f in frows:
    print(f"  @{f[1]} | followup #{f[2]} | due: {str(f[3])[:16]} | {f[4]}")

conn.close()
