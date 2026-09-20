import json
from scripts.run_acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1 import CONFIG,SCHEDULE,validate
def test_tg4_schedule_is_frozen_zero_network():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); s=json.loads(SCHEDULE.read_text(encoding='utf-8')); assert validate(c,s)==[]; assert len(s['tasks'])==40
def test_tg4_rejects_nonzero_call_counter():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); s=json.loads(SCHEDULE.read_text(encoding='utf-8')); s['model_calls']=1; assert 'schedule call counters must be zero' in validate(c,s)
