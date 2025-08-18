import os
import pytest
from backend.biomech.envelope_store import upsert_envelope, resolve_envelope


def test_round_trip_local(tmp_path, monkeypatch):
    monkeypatch.setenv('ENVELOPES_USE_GCS', 'false')
    # Force local base directory by chdir into package dir is not necessary; functions compute path relative to module
    bands = { 'release_quality': {'release_angle_deg': [30, 40]}, 'separation_sequencing': {'Δhip_torso_ms': [50, 120], 'Δtorso_hand_ms': [40, 100], 'chain_order_score_min': 0.7} }
    src = upsert_envelope('HS', 'M', 'R', bands)
    assert src in ('local','gcs')
    out, source = resolve_envelope('HS', 'M', 'R')
    assert out.get('release_quality', {}).get('release_angle_deg') == [30, 40]


@pytest.mark.skipif(os.getenv('GCS_BUCKET') is None, reason='No GCS in test env')
def test_round_trip_gcs(monkeypatch):
    monkeypatch.setenv('ENVELOPES_USE_GCS', 'true')
    bands = { 'release_quality': {'release_angle_deg': [31, 39]} }
    src = upsert_envelope('HS', 'F', 'L', bands)
    assert src == 'gcs'
    out, source = resolve_envelope('HS', 'F', 'L')
    assert source in ('gcs','local')

