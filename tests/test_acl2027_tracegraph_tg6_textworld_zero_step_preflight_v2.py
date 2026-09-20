from scripts.run_acl2027_tracegraph_tg6_textworld_zero_step_preflight_v2 import sha256


def test_sha256_is_stable(tmp_path):
    path = tmp_path / "sample"
    path.write_bytes(b"tracegraph")
    assert sha256(path) == sha256(path)
