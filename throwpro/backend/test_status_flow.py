import json
import types
from fastapi.testclient import TestClient

from backend.api.worker import app as worker_app
from backend.gcp.ingest_blur import main as ingest


def test_status_flow(monkeypatch):
    # Firestore in-memory doc
    store = {}
    class _Doc:
        def __init__(self, doc_id): self.doc_id = doc_id
        def set(self, data, merge=False):
            cur = store.get(self.doc_id, {})
            if merge:
                # shallow merge
                for k,v in data.items():
                    if isinstance(v, dict) and isinstance(cur.get(k), dict):
                        cur[k].update(v)
                    else:
                        cur[k] = v
            else:
                cur = data
            store[self.doc_id] = cur
        def get(self): return types.SimpleNamespace(exists=self.doc_id in store, to_dict=lambda: store.get(self.doc_id))
    class _FS:
        def __init__(self, project=None): pass
        def collection(self, name):
            assert name == 'throwSessions'
            return types.SimpleNamespace(document=lambda _id: _Doc(_id))

    # Stub firestore both in worker and ingest
    monkeypatch.setattr('backend.api.worker.firestore.Client', _FS)
    monkeypatch.setattr('backend.gcp.ingest_blur.main.firestore.Client', _FS)

    # Stub storage uploads/downloads no-op
    class _Blob:
        def __init__(self, name): self._name = name
        def download_to_filename(self, p): pass
        def upload_from_filename(self, p, content_type=None): pass
        def upload_from_string(self, s, content_type=None): pass
    class _Bucket:
        def blob(self, name): return _Blob(name)
    class _Storage:
        def __init__(self, *args, **kwargs): pass
        def bucket(self, name): return _Bucket()
    monkeypatch.setattr('backend.gcp.ingest_blur.main.storage.Client', _Storage)
    monkeypatch.setattr('backend.api.worker.storage.Client', _Storage)

    # Stub analyzer to be fast and deterministic
    from backend import discus_analyzer_v2 as analyzer
    monkeypatch.setattr(analyzer, 'analyze_video', lambda uri, with_coaching=False: {"pqs": {"total": 75, "components": {}}, "pqs_v2": {"components": {}}})

    # Stub overlay renderer
    from backend.visual import overlay as ov
    monkeypatch.setattr(ov, 'render_coaching_video', lambda uri, pqs, out: {"overlay_uri": out})

    # Stub pubsub publisher to directly invoke worker endpoint
    def _publish(payload: dict):
        client = TestClient(worker_app)
        body = {"message": {"data": json.dumps(payload)}, "subscription": "sub"}
        r = client.post('/pubsub', json=body)
        assert r.status_code == 204

    monkeypatch.setattr('backend.gcp.ingest_blur.main._publish_message', lambda payload: _publish(payload))

    # Seed initial session doc and call ingest with a path including sessionId prefix
    session_id = 'sess1234'
    store[session_id] = {"userId": "user1"}
    event = {"bucket": "praxisforma-videos", "name": f"incoming/user1/{session_id}__throw.mp4"}

    # Run function
    ingest.gcs_entrypoint(event, context=None)

    # Validate status transitions ended in COMPLETE
    assert store[session_id]['status']['state'] == 'COMPLETE'


