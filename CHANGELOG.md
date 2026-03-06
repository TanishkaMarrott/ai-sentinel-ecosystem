# Changelog

## [1.0.0] — 2026-04-30

### Added
- Three-agent quorum system: Safety, Audit, Cost agents running in parallel
- CloudTrail-based evidence verification for each flagged account
- Threshold enforcement: policy-based out-of-scope resource deletion
- Quarantine OU pattern — zero blast radius on source OU during enforcement
- Rollback support: `rollback_quarantine` restores accounts and removes SCP
- DEMO_MODE: realistic mock data for all tool calls, no AWS credentials needed
- GitHub Actions CI — ruff lint + pytest

### Changed
- Quorum requires 2-of-3 agreement before any SCP is applied
- Cost agent caps spend estimates at $10,000 to prevent outlier bias

### Fixed
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` must be passed explicitly to subprocess env
- SCP Sid must be alphanumeric only — hyphens cause MalformedPolicyDocumentException
