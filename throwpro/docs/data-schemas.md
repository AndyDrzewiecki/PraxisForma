# ThrowPro Data Schemas

## GCS Layout
- `gs://praxisforma-videos/incoming/{userId}/{filename}`: raw uploads (trigger)
- `gs://praxisforma-videos/blurred/{userId}/{filename}`: privacy-blurred videos (source for analysis)
- `gs://praxisforma-videos/results/{userId}/{basename}.pqs.json`: analyzer outputs for retrieval

## Firestore
Collection: `throwSessions`
Document ID: `{sessionId}`

Fields:
```
{
  userId: string,
  original_uri: string,
  blurred_uri: string,
  created_at: serverTimestamp,
  pqs: {  // exact analyzer schema
    total: number,
    components: {
      shoulder_alignment: number,
      hip_rotation: number,
      release_angle: number,
      power_transfer: number,
      footwork_timing: number
    },
    deductions: number,
    release_t_ms: number | null,
    handedness: 'left' | 'right',
    flags: string[],
    notes: string[]
  }
}
```


