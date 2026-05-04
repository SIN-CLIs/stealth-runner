from app.core import tracker, registry, compiler


def _gatekeeper_check():
    try:
        from stealth_guardian.gatekeeper import Gatekeeper
        gk = Gatekeeper()
        if not gk.request_action():
            reason = gk.get_lock_reason()
            print(f"[GUARDIAN] BLOCKED: {reason}")
            cleared = gk.wait_for_clearance()
            if cleared:
                print(f"[GUARDIAN] CLEARED after wait")
            else:
                print(f"[GUARDIAN] TIMEOUT - proceeding anyway")
        return True
    except ImportError:
        return None


def _intent_wrap(action_fn, goal, context=None):
    try:
        from stealth_memory.intent import intent_tracker
        intent_id = intent_tracker.start_intent(goal, context or {})
    except ImportError:
        intent_id = None
    result = action_fn()
    if intent_id:
        try:
            from stealth_memory.verifier import verifier
            from stealth_memory.recorder import recorder
            verdict, _ = verifier.verify(result)
            intent_tracker.resolve_intent(intent_id, verdict, result, result.get("workaround_used", False))
            recorder.record(verdict, goal)
        except ImportError:
            pass
    return result


def run(flow_name, learning_fn, payload):
    gatekeeper_ok = _gatekeeper_check()

    if registry.is_frozen(flow_name):
        from app.core.dispatcher import dispatch
        meta = registry.get(flow_name)
        tool = f"{flow_name}_v{meta['version']}"
        return dispatch(tool, payload)

    result = _intent_wrap(
        lambda: learning_fn(payload),
        goal=f"Execute survey flow: {flow_name}",
        context={"flow": flow_name, "payload_keys": list(payload.keys()) if payload else []},
    )

    if result.get("status") == "ok":
        if tracker.record(flow_name):
            compiler.compile(flow_name)

    _gatekeeper_check()
    return result