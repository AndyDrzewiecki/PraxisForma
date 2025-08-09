### Upload and Status Flow

- User starts upload from web UI. Backend returns a GCS resumable URL and `sessionId`; file is uploaded to `incoming/<uid>/<sessionId>__<filename>`.
- Cloud Function (ingest/blur) triggers on finalize:
  - Updates `throwSessions/{sessionId}.status` to `BLURRING`.
  - Blurs faces and uploads to `blurred/<uid>/<filename>`.
  - Sets status `QUEUED` and publishes a Pub/Sub message to `throwpro-analyze` with `{ sessionId, userId, blurred_uri, with_coaching, with_overlay }`.
- Cloud Run worker consumes Pub/Sub:
  - Sets `ANALYZING` → writes analysis to Firestore and `results/` JSON.
  - If coaching enabled, sets `COACHING`.
  - If overlay enabled, sets `OVERLAY`, renders MP4 to `overlays/` and writes Firestore `assets.overlay_uri`.
  - Sets `COMPLETE`.
  - On error, sets `ERROR` with `status.error`.

### Example curls

Initiate upload:

```bash
curl -X POST "$API/uploads/init" \
 -H "Authorization: Bearer $IDTOKEN" -H "Content-Type: application/json" \
 -d '{"filename":"throw.mp4","content_type":"video/mp4"}'
```

Retry processing:

```bash
curl -X POST "$API/sessions/$SESSION_ID/retry" -H "Authorization: Bearer $IDTOKEN"
```

### States

`UPLOADING → BLURRING → QUEUED → ANALYZING → COACHING → OVERLAY → COMPLETE` (or `ERROR`).

### Troubleshooting

- If upload fails, ensure Content-Range headers are sent for chunks and file is ≤200MB.
- 401 errors: verify Firebase ID token is included in `Authorization: Bearer` header.
- Forbidden: session ownership must match authenticated `uid`.
- Overlay not showing: check Firestore `assets.overlay_uri` and request a signed URL via `/signed-url`.



