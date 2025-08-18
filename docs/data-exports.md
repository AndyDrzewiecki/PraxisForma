### Data exports

Landmarks JSON (compressed)
- Path: `gs://praxisforma-videos/landmarks/<uid>/<basename>.landmarks.json`
- Content: gzipped JSON array of frames:

```
{ "timestamp_ms": int, "landmarks": [ { "x": float, "y": float, "z": null, "confidence": float }, ... ] }
```

CSV Features
- Path: `gs://praxisforma-videos/results/<uid>/<basename>.features.csv`
- Columns: `timestamp_ms` + per-frame metrics (angles, velocities, confidences). Phase labels may be included as columns.

Notes
- No PII; only anonymized kinematics.
- Target landmarks file size < 50MB (downsample/omit Z). Files are gzip-compressed.
- Overlays render within ≤1× video length.





