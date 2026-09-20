import json
from scripts.run_acl2027_tracegraph_tg2_observable_skillgraph_preflight_v1 import CONFIG,validate
def test_tg2_binds_skillbank_and_is_zero_network():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); assert validate(c)==[]; assert c['episode_execution_enabled'] is False
def test_tg2_rejects_hidden_state_input():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); c['runtime_forbidden_inputs'].remove('planner_state'); assert 'runtime forbidden inputs incomplete' in validate(c)
