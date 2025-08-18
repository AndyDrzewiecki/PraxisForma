Privacy and Ingestion Rules

Allowed inputs
- Landmarks-only workflow (no video payload, only landmark coordinates)
- Face-blurred video confirmed by pipeline metadata (session has `blurred_uri`)

Enforced checks
- Features and compare/progress endpoints require sessions to be either blurred or landmarks-only.
- On violation, API returns 400 with:
  { "error": "privacy_gate", "how_to_fix": "Upload via /upload (auto-blur) or provide landmarks-only landmarks JSON." }

Why this matters
- Protect athlete identity and comply with privacy policy.
- Ensure consistent processing and downstream sharing without facial PII.

Developer notes
- Upload flow creates sessions and triggers blur/analysis; direct analyze on raw uploads is blocked.
- Use signed URLs for any blob fetches; avoid logging PII.


