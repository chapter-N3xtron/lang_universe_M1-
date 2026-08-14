## Purpose

Define proposed evidence and recommendation semantics for verifying model capabilities across providers, local hardware, and task contexts.

## ADDED Requirements

### Requirement: Normalized capability evidence
Capability evidence SHALL use a normalized record with model/provider identity, evidence class, capability dimensions, measurement unit and method, task/context, version/configuration, source, timestamp, freshness, uncertainty, and limitations. Missing fields SHALL remain unknown rather than inferred.

#### Scenario: Evidence is imported
- **WHEN** a provider claim, benchmark, local measurement, or task result is recorded
- **THEN** it SHALL be normalized without erasing the original source class or limitations

### Requirement: Evidence classes remain distinct
The system SHALL distinguish provider claims, provider documentation, public benchmarks, local-hardware measurements, and task-specific verification. One class SHALL NOT be presented as proof of another; benchmark evidence SHALL NOT be represented as task verification, and local measurement SHALL NOT establish general provider capability.

#### Scenario: Documentation claims tool support
- **WHEN** documentation says a model supports a capability but no task verification exists
- **THEN** the recommendation SHALL label the capability as documented, not verified for the task

### Requirement: Multidimensional metrics
Verification SHALL represent relevant dimensions separately, including quality/correctness, latency, throughput, context limits, token usage, memory, compute/utilization, cost, reliability, and safety/constraint compliance where measured. A single score SHALL NOT conceal material trade-offs.

#### Scenario: Models trade quality for latency
- **WHEN** two candidates have different quality and latency measurements
- **THEN** the recommendation SHALL preserve both dimensions and explain the trade-off rather than ranking by an unexplained composite

### Requirement: Uncertainty and freshness
Evidence SHALL include uncertainty or confidence, sample/context limits, and freshness/expiry semantics. Stale, sparse, incomparable, or failed evidence SHALL lower suitability or be shown as unknown; the system SHALL not manufacture precision.

#### Scenario: Evidence is stale
- **WHEN** a capability record exceeds its freshness policy or configuration changed
- **THEN** it SHALL be marked stale or requiring re-verification and SHALL not be treated as current proof

### Requirement: Version and configuration provenance
Evidence SHALL identify model/version, provider endpoint or deployment identity where safe, runtime/configuration relevant to the measurement, hardware/software environment for local tests, task/input class, and verification reference. Recommendations SHALL be scoped to comparable versions/configurations and disclose material differences.

#### Scenario: Version changes
- **WHEN** a model version or relevant configuration changes
- **THEN** prior evidence SHALL remain historical and SHALL not silently certify the new version

### Requirement: Least-resource recommendation
Recommendations SHALL choose the least costly, least powerful, and least externally exposed option that meets the user-authorized task requirements with adequate verified evidence. “Least” SHALL consider quality, latency, reliability, resource, cost, privacy/stewardship, and failure risk; unresolved evidence SHALL require disclosure or a safer bounded option.

#### Scenario: Smaller local model is adequate
- **WHEN** a smaller local candidate meets the verified task threshold
- **THEN** it SHALL be preferred over a more resource-intensive or cloud candidate unless the user’s authorized selection says otherwise

### Requirement: No hidden escalation or hardware assumption
Verification and recommendation SHALL NOT silently escalate to a larger model, another provider, cloud execution, broader data access, or unavailable hardware. A recommendation SHALL not assume the user will purchase or provision hardware; unmet requirements SHALL be reported with explicit alternatives and authorization needs.

#### Scenario: No candidate is verified
- **WHEN** no available candidate satisfies the task requirements
- **THEN** the system SHALL report the gap and offer explicit, authorized alternatives without executing an unapproved escalation
