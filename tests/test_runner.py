import sys
sys.path.insert(0, '/Users/jeremy/dev/stealth-runner')

from runner import StealthExecutor, VisionClient, AuditLog, HumanProfile

def test_stealth_executor_init():
    e = StealthExecutor(54971, 16464)
    assert e.pid == 54971
    assert e.wid == 16464
    assert e.backend in ("skylight-cli", "cua-driver", "none")
    print(f"  backend={e.backend}")

def test_vision_client_init():
    v = VisionClient()
    assert v is not None

def test_vision_action_parsing():
    v = VisionClient()
    action = v._parse_action('{"action":"click","element_id":7}')
    assert action["action"] == "click"
    assert action["element_id"] == 7

def test_vision_action_parsing_codeblock():
    v = VisionClient()
    action = v._parse_action('```json\n{"action":"type","text":"hello"}\n```')
    assert action["action"] == "type"
    assert action["text"] == "hello"

def test_audit_log():
    a = AuditLog("/tmp/test_audit.jsonl")
    a.log("test_event", key="value")
    summary = a.get_summary()
    assert summary["total_events"] == 1

def test_human_profile():
    h = HumanProfile("test")
    assert h.profile == "test"
    assert h.min_delay > 0
    assert h.max_delay > h.min_delay

if __name__ == "__main__":
    test_stealth_executor_init()
    test_vision_client_init()
    test_vision_action_parsing()
    test_vision_action_parsing_codeblock()
    test_audit_log()
    test_human_profile()
    print("✅ ALL 6 runner tests PASSED")
