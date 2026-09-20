import json
from scripts.run_acl2027_tracegraph_tg6_local_execution_preflight_v1 import CONFIG,validate
def test_tg6_scope_is_exact_and_closed():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); assert validate(c)==[]; assert c['episode_count']==40; assert c['execution_authorized'] is False
def test_tg6_rejects_retry_scope():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); c['max_retries']=1; assert 'exact local episode scope mismatch' in validate(c)
