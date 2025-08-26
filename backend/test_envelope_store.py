from backend.biomech.envelope_store import load_active_envelope, _CACHE


def test_cache_and_fallback(monkeypatch):
    # Force firestore failure
    monkeypatch.setattr('backend.biomech.envelope_store.firestore.Client', lambda: (_ for _ in ()).throw(Exception('no fs')))  # raises when called
    env, used_fallback = load_active_envelope('discus','Open','M','right')
    assert used_fallback is True
    assert 'components' in env
    # Cached
    env2, used2 = load_active_envelope('discus','Open','M','right')
    assert used2 is False




