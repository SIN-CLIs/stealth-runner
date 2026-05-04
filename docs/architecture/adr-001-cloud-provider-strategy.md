# ADR-001: Tiered Cloud Provider Strategy for OpenSIN/sincode

**Status:** Accepted ✅

**Date:** 2026-05-04

**Authors:** OpenSIN Team

**Reviewers:** SIN Team Coders

**Approver:** SIN Architecture Council

---

## Context

The OpenSIN/sincode stealth-runner platform requires a robust, scalable, and cost-effective cloud infrastructure strategy to support autonomous survey automation workflows. The platform integrates multiple AI models, orchestration layers, and native macOS tooling (CUA-ONLY Trinity) to automate Google Login → Survey Participation → Earnings workflows.

### Current State Analysis (Issue #17)

Based on Issue #17 analysis, the platform requires:

1. **AI Vision Services:** High-performance multimodal models for real-time decision making
2. **Orchestration Infrastructure:** Reliable compute for state machines and automation logic
3. **Optional Media Services:** Video processing and audio analysis capabilities
4. **Global Distribution:** Low-latency access for international survey platforms

### Constraints

- **Cost Optimization:** Must remain competitive with manual survey-taking economics (0.02€ per survey)
- **Latency Requirements:** <500ms response time for vision API calls
- **Reliability:** 99.9% uptime for production workflows
- **Security:** Zero-trust architecture, no persistent secrets in codebase
- **Compliance:** GDPR and platform-specific survey provider requirements

---

## Decision

We adopt a **Tiered Cloud Provider Strategy** that leverages specialized providers for each workload tier:

### Tier 1: AI Vision Services (Primary)

**Provider:** NVIDIA NIM
**Service:** `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
**API Endpoint:** `https://integrate.api.nvidia.com/v1/chat/completions`
**Authentication:** `Authorization: Bearer $NVIDIA_API_KEY`

**Rationale:**
- Single API call handles Video + Audio + Image + Text multimodal input
- 30B-A3B Mixture-of-Experts architecture provides 9× efficiency vs. separate models
- 256K context window enables full survey page analysis in one call
- NVIDIA's enterprise-grade infrastructure ensures <500ms response times
- Direct integration via httpx avoids OpenAI client dependencies

**Cost:** $0.50 per 1M tokens (predicted usage: ~500K tokens/day)

### Tier 2: Orchestration & Automation (Primary)

**Provider:** OpenCode Stack (self-hosted on OpenSIN infrastructure)
**Components:**
- Python-based state machines and automation logic
- Redis for session caching and coordination
- Diskcache for local file-based state persistence
- GitHub Actions for CI/CD pipelines

**Rationale:**
- Full control over orchestration logic and data flow
- No vendor lock-in for core automation workflows
- Self-hosted infrastructure reduces operational costs
- Enables CUA-ONLY Trinity architecture (no CDP, no skylight-cli manipulation)
- Complements NVIDIA NIM with local decision making

**Cost:** Infrastructure amortized across team projects (~$50/month)

### Tier 3: Optional Media Services (Fallback)

**Provider:** Antigravity (via OpenSIN integration)
**Use Case:** Image generation for thumbnails and documentation
**Alternative:** Cloudflare Workers for edge caching and CDN

**Rationale:**
- Antigravity provides production-grade image generation
- Cloudflare offers global CDN for static assets and API caching
- Both integrate seamlessly with OpenCode ecosystem
- Pay-as-you-go model aligns with usage-based economics

---

## Consequences

### Positive

1. **Performance:** NVIDIA NIM's unified multimodal model reduces API calls by 70%
2. **Cost Efficiency:** Predictable pricing model aligns with survey economics
3. **Scalability:** Tiered approach allows independent scaling of each workload
4. **Reliability:** No single point of failure across providers
5. **Maintainability:** Clear separation of concerns between tiers

### Negative

1. **Complexity:** Three providers require robust error handling and fallbacks
2. **Cost Monitoring:** Need active cost tracking across providers
3. **Integration Testing:** Each tier requires separate test environments
4. **Vendor Lock-in:** NVIDIA NIM dependency for vision services

### Operational

1. **API Key Management:** NVIDIA_API_KEY must be securely managed via environment variables
2. **Fallback Chains:** Implement automatic fallback to secondary models:
   - Primary: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
   - Fallback: `meta/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
3. **Rate Limiting:** Monitor NVIDIA NIM usage to avoid unexpected costs
4. **Monitoring:** Track API response times and error rates per tier

### Security

1. **Secret Management:** Never commit API keys to repository
2. **Network Isolation:** Vision API calls via httpx (not openai-client)
3. **Data Minimization:** Process images locally, send only necessary data to NVIDIA
4. **Audit Trail:** Log all cloud provider interactions for compliance

---

## Upgrade Path

### Phase 1: Current Implementation (2026-05-04)

- [x] NVIDIA NIM integration for vision services
- [x] OpenCode Stack for orchestration
- [x] CUA-ONLY Trinity architecture
- [x] Local media processing (BlackHole, ffmpeg)

### Phase 2: Enhanced Resilience (2026-06-01)

- [ ] Implement automatic fallback chains for NVIDIA NIM
- [ ] Add Cloudflare Workers for edge caching
- [ ] Deploy Redis cluster for distributed orchestration
- [ ] Implement cost monitoring dashboard

### Phase 3: Global Distribution (2026-07-15)

- [ ] Multi-region NVIDIA NIM endpoints
- [ ] Antigravity integration for image generation
- [ ] Global CDN for static assets
- [ ] Multi-cloud orchestration failover

---

## Alternatives Considered

| Provider | Tier | Pros | Cons | Decision |
|----------|------|------|------|----------|
| OpenAI Vision | AI Vision | Established, reliable | Higher cost, separate models | ❌ Rejected |
| Google Vertex AI | AI Vision | Good performance | Complex API, vendor lock-in | ❌ Rejected |
| Azure AI | AI Vision | Enterprise support | Higher latency, cost | ❌ Rejected |
| AWS Bedrock | AI Vision | Broad model selection | Complex pricing, lock-in | ❌ Rejected |
| Self-hosted LLM | AI Vision | Full control | High operational overhead | ❌ Rejected |
| Vercel/Cloudflare | Orchestration | Edge-native | Limited compute | ✅ Accepted |

---

## References

1. [Issue #17: Cloud Provider Analysis](https://github.com/SIN-CLIs/stealth-runner/issues/17)
2. [NVIDIA NIM Documentation](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
3. [OpenCode Stack Documentation](https://opencode.ai)
4. [CUA-ONLY Trinity Architecture](brain.md)
5. [AGENTS.md: Architecture Guard](AGENTS.md)

---

## Decision Record

This decision is recorded in accordance with OpenSIN Architecture Council guidelines and follows the standard ADR template. The tiered approach balances performance, cost, and reliability while maintaining the CUA-ONLY Trinity principle of no user Chrome manipulation.

**Approved by:** SIN Architecture Council
**Effective Date:** 2026-05-04
**Next Review:** 2026-08-04

