"""
AI Sentinel Ecosystem — Entry Point

Three autonomous agents for AWS account governance:
  quorum   — 3-agent deliberation on abuse signals
  cost     — scan account for expensive out-of-policy resources
  recover  — dependency-aware cleanup of orphaned accounts

Usage:
  python main.py quorum                 # run quorum demo
  python main.py cost <account_id>      # run cost scan
  python main.py recover <account_id>   # run recovery
  python main.py demo                   # run all three in sequence
"""

from __future__ import annotations

import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()

console = Console()


def run_quorum_demo() -> None:
    from models.schemas import AbuseSignal
    from agents.quorum.orchestrator import QuorumOrchestrator

    signal = AbuseSignal(
        account_id="123456789012",
        lab_type="AWS_S3",
        event_type="CreateNatGateway",
        cost_estimate_usd=35.0,
        cloudtrail_events=3,
        user_id="lab-user-001",
        region="us-east-1",
    )

    console.print(Panel(
        f"[bold]Quorum Deliberation[/bold]\n"
        f"Account: {signal.account_id} | Lab: {signal.lab_type}\n"
        f"Signal: {signal.event_type} | Cost: ${signal.cost_estimate_usd}/mo",
        expand=False,
    ))

    orchestrator = QuorumOrchestrator()
    result = orchestrator.deliberate(signal)

    table = Table(title="Agent Verdicts")
    table.add_column("Agent", style="cyan")
    table.add_column("Verdict", style="bold")
    table.add_column("Confidence")
    table.add_column("Action")

    for v in result.verdicts:
        colour = "red" if v.verdict.value == "APPROVE" else "green" if v.verdict.value == "REJECT" else "yellow"
        table.add_row(v.agent_role, f"[{colour}]{v.verdict.value}[/{colour}]", f"{v.confidence:.0%}", v.recommended_action)

    console.print(table)
    console.print(Rule("Decision"))
    console.print(f"[bold]Final: {result.final_decision.upper()}[/bold] — {result.enforcement_action}")
    console.print(f"Votes to enforce: {result.votes_to_enforce} | Votes to dismiss: {result.votes_to_dismiss} | Consensus: {result.consensus_reached}")


def run_cost_scan(account_id: str) -> None:
    from agents.cost_sentinel import CostSentinelAgent

    console.print(Panel(f"[bold]Cost Sentinel Scan[/bold]\nAccount: {account_id}", expand=False))
    agent = CostSentinelAgent()
    result = agent.scan(account_id=account_id, lab_type="AWS_S3")
    console.print(Rule("Scan Result"))
    console.print(result.summary())


def run_recovery(account_id: str) -> None:
    from agents.recovery_agent import RecoveryAgent

    console.print(Panel(f"[bold]Recovery Agent[/bold]\nAccount: {account_id}", expand=False))
    agent = RecoveryAgent()
    result = agent.recover(account_id=account_id)
    console.print(Rule("Recovery Result"))
    console.print(result.summary())


def run_full_demo() -> None:
    console.print(Panel(
        "[bold]AI Sentinel Ecosystem — Full Demo[/bold]\n"
        "Quorum → Cost Sentinel → Recovery Agent",
        expand=False,
    ))
    run_quorum_demo()
    console.print()
    run_cost_scan("123456789012")
    console.print()
    run_recovery("123456789012")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    account = sys.argv[2] if len(sys.argv) > 2 else "123456789012"

    if cmd == "quorum":
        run_quorum_demo()
    elif cmd == "cost":
        run_cost_scan(account)
    elif cmd == "recover":
        run_recovery(account)
    else:
        run_full_demo()
