import json
from scripts.run_acl2027_tracegraph_tg5_runtime_runner_preflight_v1 import CONFIG,validate
def test_tg5_contract_is_zero_network_and_bound():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); assert validate(c)==[]; assert c['episode_execution_enabled'] is False
def test_tg5_rejects_multiple_trace_rows():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); c['max_trace_rows_per_task']=2; assert 'runner stop contract mismatch' in validate(c)
