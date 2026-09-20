import json
import pytest
from scripts import run_acl2027_phase3b_activation_recovery_live_v5 as live


class MockProvider:
    def __init__(self,error_at=None): self.calls,self.error_at=0,error_at
    def __call__(self,body):
        self.calls+=1
        if self.calls==self.error_at: raise TimeoutError("mock v5 timeout")
        selected=body["available_skill_ids"][-1]
        return {"content":json.dumps({"declared_skill_applicability":selected!="none","selected_skill_id":selected,"intermediate_operation":"retrieve","final_answer":"mock"}),"usage":{"input_tokens":10,"output_tokens":4,"total_tokens":14},"request_id":f"mock-v5-{self.calls}"}


def patch_artifact(tmp_path,monkeypatch):
    artifact=tmp_path/"v5"
    for name,path in {"ARTIFACT":artifact,"PREFLIGHT_AUDIT":artifact/"zero_network_preflight.json","REGISTRY":artifact/"authorization_registry.json","AUTH":artifact/"authorization_open.json","AUTH_CLOSED":artifact/"authorization_closed.json","LEDGER":artifact/"ledger.json","PACING":artifact/"request_start_ledger.json","RUN_AUDIT":artifact/"run_audit.json","CLOSURE":artifact/"authorization_closure.json"}.items():
        monkeypatch.setattr(live,name,path); monkeypatch.setattr(live.base,name,path)
    monkeypatch.setattr(live.base,"INTERVAL_NS",0)


def test_v5_preflight_binds_recovery_and_egress():
    gate=live.preflight(); assert gate["authorized_calls"]==175 and gate["recovery_aggregate_fingerprint"]=="f0c8170626d43cd97c854399b1c0b8194341b9a4034f2aba4b979d39b125cf36"
    assert gate["data_egress_authorized"] is True and gate["network_calls"]==gate["provider_calls"]==gate["paid_api_calls"]==0


def test_v5_terminal_error_is_not_resumable(tmp_path,monkeypatch):
    patch_artifact(tmp_path,monkeypatch); monkeypatch.setenv("DASHSCOPE_API_KEY","mock"); live.open_authorization()
    with pytest.raises(live.HardStop,match="mock v5 timeout"): live.execute(MockProvider(error_at=2))
    with pytest.raises(live.HardStop,match="ledger chain is not resumable"): live.execute(MockProvider())


def test_v5_receipt_rejects_fingerprint_drift(tmp_path,monkeypatch):
    receipt=live.load(live.RECEIPT); receipt["recovery_aggregate_fingerprint"]="0"*64; path=tmp_path/"receipt.json"; live.write(path,receipt); monkeypatch.setattr(live,"RECEIPT",path); monkeypatch.setattr(live.base,"RECEIPT",path)
    with pytest.raises(live.HardStop,match="receipt boundary drift"): live.preflight()
