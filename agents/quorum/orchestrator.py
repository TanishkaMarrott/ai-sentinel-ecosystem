"""
Quorum Orchestrator

Runs all three specialist agents in parallel (via threads), tallies their
verdicts, and applies majority-rules enforcement:
  - 2+ APPROVE  → enforce (quarantine SCP applied)
  - 2+ REJECT   → dismiss
  - Otherwise   → warn (flag for human review)

No single agent can enforce unilaterally. All three must be heard.
"""

from __future__ import annotations

import concurrent.futures
import os

from models.schemas import AbuseSignal, QuorumResult, Verdict
from agents.quorum.deliberation_agents import safety_agent, audit_agent, cost_agent


class QuorumOrchestrator:
    def __init__(self) -> None:
        self._max_workers = 3

    def deliberate(self, signal: AbuseSignal) -> QuorumResult:
        """
        Run 3 agents in parallel, tally verdicts, decide enforcement.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(safety_agent, signal): "safety",
                pool.submit(audit_agent, signal): "audit",
                pool.submit(cost_agent, signal): "cost",
            }
            verdicts = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    verdicts.append(future.result())
                except Exception as e:
                    # If an agent fails, treat as ABSTAIN
                    role = futures[future]
                    from models.schemas import AgentVerdict
                    verdicts.append(AgentVerdict(
                        agent_role=role,
                        verdict=Verdict.ABSTAIN,
                        confidence=0.0,
                        reasoning=f"Agent error: {e}",
                        recommended_action="review",
                    ))

        votes_enforce = sum(1 for v in verdicts if v.verdict == Verdict.APPROVE)
        votes_dismiss = sum(1 for v in verdicts if v.verdict == Verdict.REJECT)

        # Majority rules
        if votes_enforce >= 2:
            final_decision = "enforce"
            enforcement_action = f"Quarantine SCP applied to account {signal.account_id}"
            consensus_reached = True
        elif votes_dismiss >= 2:
            final_decision = "dismiss"
            enforcement_action = "No action taken — signal dismissed"
            consensus_reached = True
        else:
            final_decision = "warn"
            enforcement_action = f"Account {signal.account_id} flagged for human review"
            consensus_reached = False

        return QuorumResult(
            account_id=signal.account_id,
            verdicts=verdicts,
            final_decision=final_decision,
            votes_to_enforce=votes_enforce,
            votes_to_dismiss=votes_dismiss,
            consensus_reached=consensus_reached,
            enforcement_action=enforcement_action,
        )
