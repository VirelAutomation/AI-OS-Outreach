# Run Locally

Open two terminals.

## Terminal 1: backend

From:

`C:\Users\Marilyn\Downloads\AI OS\forge-os\backend`

Run:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' install
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

Backend default URL:

`http://localhost:8000`

## Terminal 2: frontend

From:

`C:\Users\Marilyn\Downloads\AI OS\forge-os`

Create `.env.local` with:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=
VITE_GOOGLE_CLIENT_ID=
```

Then run:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' install
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

Frontend default URL:

`http://localhost:5173`

## Important note

Use `npm.cmd`, not bare `npm`, if PowerShell execution policy blocks `npm.ps1`.
