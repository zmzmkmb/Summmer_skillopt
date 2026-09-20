import hashlib,json
from pathlib import Path
from scripts.run_acl2027_tracegraph_tg3_runtime_mechanism_preflight_v1 import CONFIG,validate

def test_tg3_binds_tg1_and_tg2_zero_network_contracts():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); assert validate(c)==[]; assert c['episode_execution_enabled'] is False

def test_tg3_rejects_skillbank_drift():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); c['skillbank_sha256']='0'*64; assert 'TG1 SkillBank fingerprint mismatch' in validate(c)
