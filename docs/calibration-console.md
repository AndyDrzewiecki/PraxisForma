### Calibration Console

Data model
- `envelopes/{event}_{ageBand}_{sex}_{handedness}_v{n}`: versioned docs with components and timing windows.
- `envelope_active/{event}_{ageBand}_{sex}_{handedness}`: pointer doc with `version`.

Admin claims
- Assign Firebase custom claim `admin=true` (or add user to Firestore `admins/{uid}`) to access admin routes.

API
- GET `/admin/envelopes/list?event=&ageBand=&sex=&handedness=`
- POST `/admin/envelopes` body: envelope (server assigns version and created_at)
- POST `/admin/envelopes/activate` body: `{event, ageBand, sex, handedness, version}`

Runtime
- Analyzer loads active envelopes via `backend/biomech/envelope_store.py` with a 5‑minute TTL cache and falls back to code constants on failure; sets `envelope_fallback` flag in outputs.

Workflow
- Create a draft → Activate to flip active pointer → Analyzer picks up new version within TTL.



