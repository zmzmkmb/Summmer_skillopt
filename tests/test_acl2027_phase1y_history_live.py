import json
import pytest

from scripts.prepare_acl2027_phase1v_calibration import HardStop
from scripts.run_acl2027_phase1y_history_live import cost_cny, execute_live, validate_live_config


class FakeProvider:
    def __init__(self, plan, private, fail=False):
        self.plan, self.private, self.fail, self.calls = plan, private, fail, 0
    def __call__(self, request):
        item = self.plan[self.calls]
        self.calls += 1
        if self.fail:
            return {"content": "{}", "usage": None}
        gold = self.private[item["logical_call_id"]]
        body = {"answer": gold["answers"][0]}
        if item["task_family"] == "2WikiMultiHopQA":
            body["supporting_evidence"] = gold["supporting_evidence"]
        return {"content": json.dumps(body), "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}


def test_exact_authorized_plan_and_no_max_tokens():
    config, plan, private = validate_live_config()
    assert len(plan) == len(private) == config["authorization"]["authorized_calls"] == 10
    assert all("max_tokens" not in row["request"] for row in plan)
    assert config["execution"]["sdk_max_retries"] == config["execution"]["explicit_retries"] == 0


def test_verified_results_and_resume(tmp_path):
    config, plan, private = validate_live_config()
    provider = FakeProvider(plan, private)
    first = execute_live(config, plan, private, tmp_path, provider, max_new_calls=3)
    final = execute_live(config, plan, private, tmp_path, provider)
    assert first["recorded_calls"] == 3
    assert final["recorded_calls"] == final["verified_trajectories"] == 10
    assert final["verified_by_family"] == {"SearchQA": 2, "2WikiMultiHopQA": 8}


def test_unknown_usage_is_terminal(tmp_path):
    config, plan, private = validate_live_config()
    assert execute_live(config, plan, private, tmp_path, FakeProvider(plan, private, True))["status"] == "hard_stopped"
    with pytest.raises(HardStop, match="not resumable"):
        execute_live(config, plan, private, tmp_path, FakeProvider(plan, private))


def test_local_cost_has_no_request_token_limit():
    config, _, _ = validate_live_config()
    assert cost_cny(config, {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}) == pytest.approx(10.0)
    assert config["cost_control"]["ceiling_is_request_parameter"] is False
