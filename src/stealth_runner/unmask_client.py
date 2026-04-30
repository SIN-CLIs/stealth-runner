"""unmask-cli JSON-RPC 2.0 Client für Stealth-Verifikation."""
from __future__ import annotations
import httpx
from enum import StrEnum, auto
from .config import StealthConfig
import structlog

log = structlog.get_logger()

class StealthStatus(StrEnum):
    PASS = auto(); WARN = auto(); FAIL = auto()

async def verify_stealth(cfg: StealthConfig, url: str, timeout: float = 6.0) -> StealthStatus:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            dom_resp = await client.post(cfg.unmask_rpc_url, json={"jsonrpc":"2.0","id":1,"method":"dom.scan","params":{"url":url}})
            dom_data = dom_resp.json().get("result", {})
            con_resp = await client.post(cfg.unmask_rpc_url, json={"jsonrpc":"2.0","id":2,"method":"console.list","params":{}})
            con_data = con_resp.json().get("result", [])
            net_resp = await client.post(cfg.unmask_rpc_url, json={"jsonrpc":"2.0","id":3,"method":"network.list","params":{}})
            net_data = net_resp.json().get("result", [])
            
            error_count = sum(1 for c in con_data if c.get("type") in ("error","pageerror"))
            suspicious_network = sum(1 for n in net_data if n.get("status",200) >= 400)
            elements = dom_data.get("elements", [])
            element_confidence_avg = sum(e.get("confidence",0) for e in elements) / max(len(elements), 1)
            
            score = 100
            score -= min(error_count * 10, 30)
            score -= min(suspicious_network * 5, 20)
            score -= max(0, int((0.8 - element_confidence_avg) * 50))
            
            log.info("unmask_check", url=url, score=score)
            if score >= 85: return StealthStatus.PASS
            if score >= 70: return StealthStatus.WARN
            return StealthStatus.FAIL
    except Exception as e:
        log.warning("unmask_verification_failed", error=str(e))
        return StealthStatus.WARN
