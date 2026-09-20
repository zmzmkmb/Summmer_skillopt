from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
def test_phase5_live_preflight_closed():
    p=subprocess.run([sys.executable,"scripts/run_acl2027_phase5_admission_grounding_live_preflight_v1.py"],cwd=ROOT,text=True,capture_output=True,check=True)
    payload=json.loads(p.stdout)
    assert payload["result"]["status"]=="live-execution-preflight-passed-closed"
    assert payload["result"]["schedule_audit"]["rows"]==240
    assert payload["authorization_request"]["status"]=="awaiting_exact_explicit_user_authorization"