import hashlib, json
from pathlib import Path
from scripts.run_acl2027_tracegraph_tg1_skillbank_construction_preflight_v2 import CONFIG, MANIFEST, validate

def test_enabled_preflight_binds_manifest_and_remains_zero_network():
    config=json.loads(CONFIG.read_text(encoding="utf-8")); manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert validate(config,manifest)==[]
    assert config["construction_enabled"] is True
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest()==config["source_manifest_sha256"]

def test_preflight_rejects_manifest_drift():
    config=json.loads(CONFIG.read_text(encoding="utf-8")); manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    config["source_manifest_sha256"]="0"*64
    assert "source manifest fingerprint mismatch" in validate(config,manifest)
