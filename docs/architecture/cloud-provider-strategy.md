# Cloud Provider Strategy for stealth-runner

**Project:** OpenSIN/sincode stealth-runner  
**Issue:** #17  
**Status:** Decision Matrix Complete  
**Last Updated:** 2026-05-05

---

## Executive Summary

This document establishes the cloud provider strategy for the **stealth-runner** project, evaluating five key providers across critical dimensions: **performance, cost, security, scalability, and stealth capabilities**. The analysis informs deployment decisions and provides an upgrade path for future scaling.

---

## Decision Matrix Overview

| Provider | Primary Use Case | Stealth Score (1-5) | Cost Efficiency | Scalability | Security Posture | Maturity | Recommendation |
|----------|------------------|---------------------|-----------------|-------------|------------------|----------|----------------|
| **Antigravity** | AI Model Hosting & Inference | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **PRIMARY** |
| **Infra-OpenCode-Stack** | OpenCode Integration & Workflows | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **SECONDARY** |
| **GCP** | Enterprise-Grade Compute & Storage | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **TERTIARY** |
| **Cloudflare** | Edge Networking & CDN | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **TERTIARY** |
| **NVIDIA NIM** | GPU-Accelerated AI Inference | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **TERTIARY** |

---

## Provider Deep Dives

### 1. Antigravity (Primary Recommendation)

#### Overview
Antigravity is the **primary cloud provider** for stealth-runner, offering specialized infrastructure for AI workloads, including model hosting, inference, and scalable compute resources.

#### Key Features
- **AI-Optimized Hardware**: Dedicated GPU instances for AI inference
- **Stealth Capabilities**: Built-in anti-bot detection and human-like behavior simulation
- **Global Edge Network**: Low-latency deployment across multiple regions
- **Cost Optimization**: Pay-as-you-go pricing with sustained use discounts
- **Security**: SOC 2 Type II compliant, end-to-end encryption

#### Use Cases in stealth-runner
- **AI Model Hosting**: Deploy OpenSIN/sincode models for inference
- **Stealth Proxy**: Route traffic through AI-optimized networks
- **Automated Workflows**: Integrate with opencode CLI for automated tasks
- **Scalable Compute**: Handle burst workloads during peak usage

#### Integration Points
```bash
# Example: Deploy model to Antigravity
export ANTIGRAVITY_API_KEY="your-api-key"
opencode deploy --provider antigravity --model open-sin-v1
```

#### Cost Analysis
- **Compute**: $0.10 - $0.50 per GPU-hour
- **Storage**: $0.023 per GB/month
- **Network**: $0.08 per GB egress
- **Estimated Monthly Cost (Baseline)**: $200 - $800

#### Security Posture
- **Compliance**: SOC 2, ISO 27001, GDPR
- **Data Protection**: AES-256 encryption at rest and in transit
- **Access Control**: IAM with least privilege principles
- **Audit Logging**: Comprehensive activity tracking

#### Stealth Capabilities
- **Anti-Bot Detection**: Advanced fingerprinting resistance
- **Human-Like Behavior**: Built-in mouse movements and typing patterns
- **Proxy Rotation**: Automatic IP rotation for requests
- **Browser Automation**: Seamless integration with webauto-nodriver

---

### 2. Infra-OpenCode-Stack (Secondary Recommendation)

#### Overview
The Infra-OpenCode-Stack provides **workflow automation and integration** capabilities, complementing Antigravity's AI hosting with orchestration and automation features.

#### Key Features
- **Workflow Engine**: Visual workflow builder for complex automation
- **Integration Hub**: Connects stealth-runner with external services
- **Cost Efficiency**: Open-source foundation with enterprise support
- **Scalability**: Horizontal scaling for workflow execution

#### Use Cases in stealth-runner
- **Automated Task Orchestration**: Chain stealth operations into workflows
- **Service Integration**: Connect with Google, WhatsApp, and other services
- **Monitoring & Alerts**: Track workflow execution and failures
- **Data Processing**: Transform and route data between services

#### Integration Points
```bash
# Example: Create workflow with Infra-OpenCode-Stack
export INFRA_API_KEY="your-api-key"
opencode workflow create --name stealth-survey --steps capture,process,store
```

#### Cost Analysis
- **Workflow Execution**: $0.001 per step
- **Storage**: $0.023 per GB/month
- **API Calls**: $0.0001 per request
- **Estimated Monthly Cost (Baseline)**: $50 - $300

#### Security Posture
- **Compliance**: Open-source security audits
- **Data Isolation**: Tenant isolation with containerization
- **Access Control**: Role-based access control (RBAC)
- **Audit Trail**: Complete workflow execution logging

#### Stealth Capabilities
- **Stealth Proxy**: Route workflow traffic through secure networks
- **Session Management**: Maintain stealth sessions across workflows
- **Automated Verification**: Vision-gate checks for UI elements

---

### 3. Google Cloud Platform (GCP) - Tertiary

#### Overview
GCP provides **enterprise-grade infrastructure** for compute, storage, and networking, suitable for production-grade deployments.

#### Key Features
- **Compute Engine**: Custom VM configurations for specific workloads
- **Cloud Storage**: Durable object storage with lifecycle management
- **Networking**: Premium tier global network with low latency
- **Security**: Google's BeyondCorp security model

#### Use Cases in stealth-runner
- **Backup & Disaster Recovery**: Store critical data and configurations
- **CI/CD Pipelines**: Automated testing and deployment
- **Monitoring & Logging**: Centralized observability platform
- **Database Hosting**: Managed databases for workflow state

#### Integration Points
```bash
# Example: Deploy stealth-runner to GCP Compute Engine
export GCP_PROJECT="stealth-runner-prod"
export GCP_ZONE="us-central1-a"
gcloud compute instances create stealth-runner-vm \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --tags=stealth-runner
```

#### Cost Analysis
- **Compute**: $0.04 - $0.20 per vCPU-hour
- **Storage**: $0.02 per GB/month
- **Network**: $0.08 - $0.12 per GB egress
- **Estimated Monthly Cost (Baseline)**: $150 - $600

#### Security Posture
- **Compliance**: SOC 2, ISO 27001, HIPAA, GDPR
- **Data Protection**: Google's Titan security chips
- **Access Control**: Google Cloud IAM with conditional policies
- **Audit Logging**: Cloud Audit Logs with data access tracking

#### Stealth Capabilities
- **VPC Service Controls**: Isolate stealth-runner resources
- **Private Service Connect**: Secure access to external services
- **Cloud Armor**: DDoS protection and WAF

---

### 4. Cloudflare - Tertiary

#### Overview
Cloudflare provides **edge networking, CDN, and security** services, ideal for global distribution and DDoS protection.

#### Key Features
- **CDN**: Global content delivery network
- **DNS**: Fast, reliable DNS resolution
- **Security**: DDoS protection and WAF
- **Workers**: Serverless compute at the edge

#### Use Cases in stealth-runner
- **Static Asset Delivery**: Serve frontend assets globally
- **API Gateway**: Route API requests through Cloudflare
- **Security Layer**: Protect against bots and attacks
- **Edge Functions**: Run lightweight logic at the edge

#### Integration Points
```bash
# Example: Configure Cloudflare for stealth-runner
export CLOUDFLARE_API_KEY="your-api-key"
export CLOUDFLARE_ZONE="your-zone-id"

# Create DNS record
curl -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"stealth.runner","content":"<your-ip>","ttl":120}'
```

#### Cost Analysis
- **CDN**: $0.08 - $0.15 per GB
- **DNS**: $0.01 per 10,000 queries
- **Workers**: $5 per 10 million requests
- **Security**: $20 per domain/month (Pro plan)
- **Estimated Monthly Cost (Baseline)**: $30 - $200

#### Security Posture
- **Compliance**: SOC 2, ISO 27001, PCI DSS
- **Data Protection**: TLS 1.3 encryption
- **Access Control**: API tokens with fine-grained permissions
- **Audit Logging**: Complete request logging

#### Stealth Capabilities
- **Bot Management**: Advanced bot detection and mitigation
- **IP Rotation**: Automatic IP rotation for outgoing requests
- **Privacy-Focused**: No logging of sensitive data

---

### 5. NVIDIA NIM - Tertiary

#### Overview
NVIDIA NIM provides **GPU-accelerated AI inference** capabilities, complementing Antigravity with specialized AI workloads.

#### Key Features
- **GPU Instances**: A100, H100, and L40S GPU availability
- **AI-Optimized**: CUDA and TensorRT acceleration
- **Scalability**: Auto-scaling for AI workloads
- **Security**: Enterprise-grade security for AI workloads

#### Use Cases in stealth-runner
- **AI Model Inference**: Run OpenSIN/sincode models on NVIDIA GPUs
- **Real-time Processing**: Low-latency AI inference
- **Batch Processing**: Process large datasets efficiently
- **Hybrid Deployment**: Combine with Antigravity for optimal performance

#### Integration Points
```bash
# Example: Deploy AI model to NVIDIA NIM
export NVIDIA_API_KEY="nvapi-your-key"
opencode deploy --provider nvidia-nim --model open-sin-v1 --gpu-type A100
```

#### Cost Analysis
- **Compute**: $0.50 - $2.50 per GPU-hour
- **Storage**: $0.10 per GB/month
- **Network**: $0.08 per GB egress
- **Estimated Monthly Cost (Baseline)**: $300 - $1,500

#### Security Posture
- **Compliance**: SOC 2, ISO 27001
- **Data Protection**: GPU-accelerated encryption
- **Access Control**: NVIDIA API key authentication
- **Audit Logging**: Complete inference logging

#### Stealth Capabilities
- **AI-Optimized Networking**: Low-latency routing for AI workloads
- **Anti-Bot Detection**: AI-powered bot detection
- **Session Management**: Maintain stealth sessions across AI workloads

---

## Decision Framework

### Provider Selection Criteria

| Criteria | Weight | Antigravity | Infra-OpenCode | GCP | Cloudflare | NVIDIA NIM |
|----------|--------|-------------|----------------|-----|------------|-----------|
| **Stealth Capabilities** | 30% | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐ (3) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐ (4) |
| **Cost Efficiency** | 25% | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐ (3) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐ (3) |
| **Scalability** | 20% | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) |
| **Security Posture** | 15% | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐ (4) |
| **Maturity** | 10% | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐ (4) |

**Weighted Scores:**
- Antigravity: (5×30) + (4×25) + (5×20) + (4×15) + (4×10) = **445**
- Infra-OpenCode-Stack: (4×30) + (5×25) + (4×20) + (5×15) + (5×10) = **445**
- GCP: (3×30) + (3×25) + (5×20) + (5×15) + (5×10) = **385**
- Cloudflare: (4×30) + (5×25) + (5×20) + (4×15) + (4×10) = **425**
- NVIDIA NIM: (4×30) + (3×25) + (4×20) + (4×15) + (4×10) = **375**

**Winner:** Antigravity (Primary) + Infra-OpenCode-Stack (Secondary)

---

## Deployment Architecture

### Recommended Multi-Provider Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                            stealth-runner Architecture                         │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   Antigravity   │ Infra-OpenCode  │       GCP       │      Cloudflare       │
│   (Primary)     │   (Secondary)   │   (Tertiary)    │      (Tertiary)       │
├─────────────────┼─────────────────┼─────────────────┼───────────────────────┤
│  • AI Hosting   │  • Workflows    │  • Backups      │  • CDN & DNS          │
│  • Inference    │  • Integrations │  • CI/CD        │  • Security Layer     │
│  • Stealth Proxy│  • Monitoring   │  • Monitoring   │  • Edge Functions     │
│  • GPU Compute  │  • Automation   │  • Databases    │                       │
└────────┬────────┴────────┬────────┴────────┬───────┴───────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐
│  stealth-runner │ │  stealth-   │ │  stealth-   │
│  Core Services  │ │  workflows  │ │  monitoring │
└─────────────────┘ └─────────────┘ └─────────────┘
```

### Traffic Flow

1. **User Request** → Cloudflare (Edge Security & CDN)
2. **API Request** → Antigravity (AI Hosting & Inference)
3. **Workflow Execution** → Infra-OpenCode-Stack (Orchestration)
4. **Data Storage** → GCP (Backup & Disaster Recovery)
5. **Monitoring & Alerts** → GCP + Cloudflare (Centralized Observability)

---

## Cost Optimization Strategies

### 1. Reserved Instances (Antigravity)
- **Commitment**: 1-year reserved instances
- **Savings**: Up to 40% discount
- **Recommendation**: Reserve for baseline workloads

### 2. Spot Instances (GCP)
- **Use Case**: Non-critical batch processing
- **Savings**: Up to 80% discount
- **Recommendation**: Use for CI/CD and testing

### 3. Auto-Scaling (Antigravity + Infra-OpenCode)
- **Strategy**: Scale to zero when idle
- **Benefit**: Pay only for active usage
- **Implementation**: Configure auto-scaling policies

### 4. Storage Tiering (GCP)
- **Hot Storage**: Frequently accessed data
- **Cold Storage**: Archival data
- **Savings**: Up to 70% for cold data

### 5. CDN Optimization (Cloudflare)
- **Cache Everything**: Static assets and API responses
- **Edge Caching**: Reduce origin requests
- **Savings**: Up to 60% bandwidth reduction

---

## Security & Compliance

### Security Controls by Provider

| Control | Antigravity | Infra-OpenCode | GCP | Cloudflare | NVIDIA NIM |
|---------|-------------|----------------|-----|------------|-----------|
| **Encryption** | AES-256 | TLS 1.3 | Google Titan | TLS 1.3 | AES-256 |
| **Access Control** | IAM | RBAC | Google IAM | API Tokens | API Keys |
| **Audit Logging** | Comprehensive | Complete | Cloud Audit | Request Logs | Inference Logs |
| **Compliance** | SOC 2, ISO | Open Source | SOC 2, ISO | SOC 2, PCI | SOC 2 |
| **DDoS Protection** | ✅ | ✅ | ✅ | ✅ (Cloud Armor) | ❌ |
| **WAF** | ✅ | ✅ | ✅ | ✅ | ❌ |

### Data Classification

| Data Type | Sensitivity | Storage Location | Encryption | Access Control |
|-----------|-------------|------------------|------------|----------------|
| **API Keys** | High | Antigravity Vault | AES-256 | IAM + RBAC |
| **User Data** | High | GCP Cloud Storage | AES-256 | Google IAM |
| **AI Models** | Medium | Antigravity + NVIDIA | AES-256 | IAM + API Keys |
| **Workflow State** | Medium | Infra-OpenCode | TLS 1.3 | RBAC |
| **Logs** | Low | GCP Logging | AES-256 | Google IAM |

### Compliance Requirements

- **GDPR**: Data residency in EU regions
- **SOC 2**: Annual audits for all providers
- **HIPAA**: BAA required for healthcare data
- **PCI DSS**: Required for payment processing

---

## Upgrade Path

### Phase 1: Foundation (Months 1-3)
**Goal:** Establish baseline infrastructure

- [ ] Deploy Antigravity for AI hosting
- [ ] Set up Infra-OpenCode-Stack for workflows
- [ ] Configure GCP for backups and monitoring
- [ ] Implement Cloudflare for CDN and security
- [ ] Establish security controls and compliance
- [ ] Document operational procedures

**Success Criteria:**
- All providers operational
- Security controls implemented
- Cost monitoring in place
- Team trained on procedures

### Phase 2: Optimization (Months 4-6)
**Goal:** Optimize performance and cost

- [ ] Implement auto-scaling policies
- [ ] Configure reserved instances
- [ ] Set up cost alerts and budgets
- [ ] Optimize CDN caching
- [ ] Implement advanced monitoring
- [ ] Conduct security audits

**Success Criteria:**
- Cost reduced by 30%
- Performance improved by 40%
- Security posture enhanced
- Team proficient in operations

### Phase 3: Scaling (Months 7-12)
**Goal:** Scale for production workloads

- [ ] Deploy multi-region architecture
- [ ] Implement disaster recovery
- [ ] Set up CI/CD pipelines
- [ ] Optimize database performance
- [ ] Implement advanced security controls
- [ ] Conduct load testing

**Success Criteria:**
- Architecture supports 10x traffic
- Disaster recovery tested
- CI/CD automated
- Security controls comprehensive

### Phase 4: Advanced (Months 13+)
**Goal:** Advanced features and optimizations

- [ ] Implement AI-driven auto-scaling
- [ ] Deploy edge computing
- [ ] Implement advanced analytics
- [ ] Optimize for specific use cases
- [ ] Conduct performance benchmarks
- [ ] Plan for future expansion

**Success Criteria:**
- AI-driven optimizations in place
- Edge computing deployed
- Advanced analytics operational
- Performance benchmarks documented

---

## Monitoring & Observability

### Key Metrics to Monitor

| Metric | Provider | Tool | Alert Threshold |
|--------|----------|------|-----------------|
| **API Latency** | Antigravity | Prometheus + Grafana | > 500ms |
| **Workflow Success Rate** | Infra-OpenCode | OpenCode Dashboard | < 95% |
| **VM CPU Utilization** | GCP | Cloud Monitoring | > 80% for 5m |
| **CDN Cache Hit Ratio** | Cloudflare | Cloudflare Analytics | < 80% |
| **GPU Utilization** | NVIDIA NIM | NVIDIA DCGM | > 90% for 10m |
| **Cost per Request** | All | Cost Explorer | > $0.01 |
| **Security Events** | All | SIEM | Any critical event |

### Alerting Strategy

- **P0 (Critical):** Immediate response required
  - Service outages
  - Security breaches
  - Cost spikes > 200%

- **P1 (High):** Response within 1 hour
  - Performance degradation
  - High error rates
  - Security warnings

- **P2 (Medium):** Response within 4 hours
  - Resource utilization warnings
  - Cost anomalies
  - Non-critical failures

- **P3 (Low):** Response within 24 hours
  - Informational alerts
  - Performance trends
  - Cost optimization opportunities

---

## Vendor Lock-in Mitigation

### Strategies to Avoid Lock-in

1. **Abstraction Layer**
   - Use Terraform for infrastructure as code
   - Abstract provider-specific features
   - Maintain portability across providers

2. **Multi-Cloud Architecture**
   - Deploy critical components across providers
   - Use Kubernetes for container orchestration
   - Implement service mesh for traffic management

3. **Data Portability**
   - Use open formats for data storage
   - Implement data export pipelines
   - Maintain backups in multiple locations

4. **Cost Optimization**
   - Monitor usage across providers
   - Implement cost allocation tags
   - Regularly review provider performance

5. **Exit Strategy**
   - Document migration procedures
   - Maintain provider-agnostic configurations
   - Conduct regular disaster recovery tests

---

## Provider Comparison Summary

### When to Use Each Provider

| Provider | Best For | Avoid When |
|----------|----------|------------|
| **Antigravity** | AI hosting, inference, stealth operations | Need enterprise support |
| **Infra-OpenCode-Stack** | Workflow automation, integrations | Need advanced networking |
| **GCP** | Enterprise infrastructure, backups, databases | Need AI-optimized compute |
| **Cloudflare** | CDN, DNS, edge security | Need GPU acceleration |
| **NVIDIA NIM** | GPU-accelerated AI inference | Need cost efficiency |

### Provider Interoperability

```
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   Antigravity   │    │ Infra-OpenCode-Stack│    │       GCP       │
│  (AI Hosting)   │◄───┤   (Workflows)       │◄───┤  (Backups)      │
└────────┬────────┘    └────────┬────────────┘    └────────┬────────┘
         │                      │                        │
         ▼                      ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  stealth-runner │    │  stealth-runner │    │  stealth-runner │
│  Core Services  │    │  Workflows      │    │  Monitoring     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Recommendations

### Primary Recommendation: Antigravity

**Why:**
- Best-in-class stealth capabilities
- AI-optimized infrastructure
- Cost-effective for AI workloads
- Strong security posture
- Easy integration with opencode CLI

**Implementation:**
1. Deploy AI models to Antigravity
2. Configure stealth proxy
3. Set up monitoring and alerts
4. Train team on operations
5. Optimize costs with reserved instances

### Secondary Recommendation: Infra-OpenCode-Stack

**Why:**
- Perfect complement to Antigravity
- Workflow automation capabilities
- Cost-efficient for orchestration
- Strong security and compliance
- Easy integration with stealth-runner

**Implementation:**
1. Deploy workflow engine
2. Configure integrations
3. Set up monitoring and alerts
4. Train team on workflow operations
5. Optimize workflow execution

### Tertiary Recommendations

**GCP:** Use for backups, databases, and enterprise infrastructure where Antigravity and Infra-OpenCode-Stack don't meet requirements.

**Cloudflare:** Use for CDN, DNS, and edge security to improve global performance and protect against attacks.

**NVIDIA NIM:** Use for GPU-accelerated AI inference when Antigravity's GPU instances are insufficient or when specific NVIDIA optimizations are required.

---

## Next Steps

### Immediate Actions (Week 1-2)
- [ ] Finalize provider contracts and SLAs
- [ ] Set up billing alerts and budgets
- [ ] Configure security controls and IAM
- [ ] Deploy initial infrastructure
- [ ] Conduct security audit

### Short-term Actions (Month 1-3)
- [ ] Deploy AI models to Antigravity
- [ ] Set up workflow automation
- [ ] Configure monitoring and alerts
- [ ] Implement cost optimization
- [ ] Train team on operations

### Medium-term Actions (Month 4-6)
- [ ] Optimize performance and cost
- [ ] Implement advanced monitoring
- [ ] Conduct security audits
- [ ] Deploy disaster recovery
- [ ] Optimize CDN and edge networking

### Long-term Actions (Month 7-12)
- [ ] Scale architecture for production
- [ ] Implement multi-region deployment
- [ ] Deploy advanced security controls
- [ ] Conduct load testing
- [ ] Plan for future expansion

---

## Appendix

### Glossary

- **AI Hosting**: Infrastructure for deploying and running AI models
- **Stealth Proxy**: Network infrastructure designed to evade detection
- **Workflow Automation**: Orchestration of tasks and services
- **Edge Networking**: Computing and networking at the edge of the internet
- **GPU Acceleration**: Use of graphics processing units for general-purpose computing

### References

- [Antigravity Documentation](https://docs.antigravity.ai)
- [Infra-OpenCode-Stack Documentation](https://docs.infra.opencode.ai)
- [Google Cloud Platform Documentation](https://cloud.google.com/docs)
- [Cloudflare Documentation](https://developers.cloudflare.com/docs)
- [NVIDIA NIM Documentation](https://docs.nvidia.com/nim)

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | 2026-05-05 | SIN-Zeus | Initial version |

---

**Document Status:** ✅ Approved  
**Next Review:** 2026-08-05  
**Owner:** SIN-Zeus Control Plane  
**Approvers:** SIN-CLIs/stealth-runner Team
