from scripts import run_acl2027_phase3e_control_validity_audit_v1 as phase
def test_phase3e_finds_structural_bridge_control_failure():
 r=phase.audit(); assert r['status']=='complete'; assert r['control_validity']['attribute_comparison_control_valid'] is True; assert r['control_validity']['bridge_attribute_comparison_control_valid'] is False; assert r['irrelevant_single_by_family']['bridge_attribute_comparison']['applicable_count']==13; assert r['network_calls']==r['provider_calls']==0
