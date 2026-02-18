"""CLI entry point for stratus framework."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import cast

from stratus import __version__
from stratus.mcp_server.server import main as mcp_main
from stratus.server.runner import run_server
from stratus.transcript import (
    estimate_context_pct,
    find_compaction_events,
    parse_transcript,
    to_effective_pct,
)


def _cmd_analyze(args: argparse.Namespace) -> None:
    transcript = cast(Path, args.transcript)
    window = cast(int, args.context_window)

    if not transcript.exists():
        print(f"Error: file not found: {transcript}", file=sys.stderr)
        sys.exit(1)

    stats = parse_transcript(transcript)
    events = find_compaction_events(transcript)

    print(f"Transcript: {transcript.name}")
    print(f"Context window: {window:,}")
    print(f"Messages:   {stats.message_count}")
    print(f"Peak tokens: {stats.peak_tokens:,}")
    print(f"Final tokens: {stats.final_tokens:,}")

    if stats.peak_tokens > 0:
        raw_pct = estimate_context_pct(stats.peak_tokens, context_window=window)
        eff_pct = to_effective_pct(raw_pct)
        print(f"Peak context: {raw_pct:.1f}% raw, {eff_pct:.1f}% effective")

    if events:
        print(f"\nCompaction events: {len(events)}")
        for i, event in enumerate(events, 1):
            pct = estimate_context_pct(event.pre_tokens, context_window=window)
            line = (
                f"  {i}. {event.timestamp} | {event.pre_tokens:,} tokens"
                f" ({pct:.1f}%) | trigger: {event.trigger}"
            )
            print(line)
    else:
        print("\nNo compaction events found.")


def _cmd_init(args: argparse.Namespace) -> None:
    from stratus.bootstrap.commands import cmd_init

    cmd_init(args)


def _cmd_doctor(args: argparse.Namespace) -> None:
    from stratus.bootstrap.commands import cmd_doctor

    cmd_doctor(args)


def _cmd_serve(_args: argparse.Namespace) -> None:
    run_server()


def _cmd_mcp_serve(_args: argparse.Namespace) -> None:
    mcp_main()


def _cmd_reindex(args: argparse.Namespace) -> None:
    from stratus.retrieval.config import load_retrieval_config
    from stratus.retrieval.vexor import VexorClient

    config = load_retrieval_config()
    client = VexorClient(config.vexor)

    if not client.is_available():
        print("Error: Vexor binary not available", file=sys.stderr)
        sys.exit(1)

    clear: bool = hasattr(args, "full") and bool(args.full)  # type: ignore[reportAny]
    result: dict[str, object] = client.index(clear=clear)  # type: ignore[reportUnknownMemberType]
    if result.get("status") == "ok":
        print(f"Reindex complete: {result.get('output', '')}")
    else:
        print(f"Reindex failed: {result.get('message', 'unknown error')}", file=sys.stderr)
        sys.exit(1)


def _cmd_retrieval_status(_args: argparse.Namespace) -> None:
    from stratus.retrieval.unified import UnifiedRetriever

    retriever = UnifiedRetriever()
    status: dict[str, object] = retriever.status()  # type: ignore[reportUnknownMemberType]

    print("Retrieval Status:")
    print(f"  Vexor:  {'available' if status['vexor_available'] else 'unavailable'}")
    print(f"  DevRag: {'available' if status['devrag_available'] else 'unavailable'}")


def _cmd_worktree(args: argparse.Namespace) -> None:
    import json as json_mod

    from stratus.hooks._common import get_git_root
    from stratus.orchestration import worktree
    from stratus.orchestration.worktree import WorktreeError

    git_root = get_git_root()
    if git_root is None:
        print("Error: not in a git repository", file=sys.stderr)
        sys.exit(1)

    slug = cast(str, args.slug)
    plan_path = cast(str, args.plan_path)
    base_branch = cast(str, args.base_branch)
    action = cast(str, args.action)
    try:
        if action == "detect":
            result = worktree.detect(slug, git_root, plan_path=plan_path, base_branch=base_branch)
        elif action == "create":
            result = worktree.create(slug, git_root, plan_path=plan_path, base_branch=base_branch)
        elif action == "diff":
            print(worktree.diff(slug, git_root, plan_path=plan_path))
            return
        elif action == "sync":
            result = worktree.sync(slug, git_root, plan_path=plan_path)
        elif action == "cleanup":
            result = worktree.cleanup(slug, git_root, plan_path=plan_path)
        elif action == "status":
            result = worktree.status(slug, git_root, plan_path=plan_path, base_branch=base_branch)
        else:
            print(f"Error: unknown action: {action}", file=sys.stderr)
            sys.exit(1)

        print(json_mod.dumps(result, indent=2))  # type: ignore[reportUnknownArgumentType]
    except WorktreeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_hook(args: argparse.Namespace) -> None:
    mod = importlib.import_module(f"stratus.hooks.{args.module}")
    mod.main()


def _cmd_learning(args: argparse.Namespace) -> None:
    from stratus.learning.commands import cmd_learning

    cmd_learning(args)


def _is_jsonl_path(arg: str) -> bool:
    return arg.endswith(".jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stratus",
        description="Open-source framework for Claude Code sessions",
    )
    _ = parser.add_argument(
        "-V", "--version", action="version", version=f"stratus {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a JSONL transcript")
    _ = analyze_parser.add_argument("transcript", type=Path, help="Path to .jsonl transcript file")
    _ = analyze_parser.add_argument(
        "--context-window",
        type=int,
        default=200_000,
        help="Context window size in tokens (default: 200000)",
    )

    # init subcommand
    init_p = subparsers.add_parser("init", help="Initialize project bootstrap")
    _ = init_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print actions without writing",
    )
    _ = init_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .ai-framework.json",
    )
    _ = init_p.add_argument(
        "--skip-hooks",
        action="store_true",
        dest="skip_hooks",
        help="Skip hook registration in .claude/settings.json",
    )
    _ = init_p.add_argument(
        "--skip-mcp",
        action="store_true",
        dest="skip_mcp",
        help="Skip MCP server registration in .mcp.json",
    )
    _ = init_p.add_argument(
        "--skip-retrieval",
        action="store_true",
        dest="skip_retrieval",
        help="Skip retrieval backend detection and setup",
    )
    _ = init_p.add_argument(
        "--enable-delivery",
        action="store_true",
        dest="enable_delivery",
        help="Enable delivery framework and install runtime agents",
    )
    _ = init_p.add_argument(
        "--skip-agents",
        action="store_true",
        dest="skip_agents",
        help="Skip runtime agent installation",
    )
    _ = init_p.add_argument(
        "--scope",
        choices=["local", "global"],
        default=None,
        help="Installation scope: local (project) or global (~/.claude/)",
    )

    # doctor subcommand
    _ = subparsers.add_parser("doctor", help="Run health checks on all components")

    # serve subcommand
    _ = subparsers.add_parser("serve", help="Start the HTTP API server")

    # mcp-serve subcommand
    _ = subparsers.add_parser("mcp-serve", help="Start the MCP stdio server")

    # reindex subcommand
    reindex_parser = subparsers.add_parser("reindex", help="Trigger code reindexing")
    _ = reindex_parser.add_argument("--full", action="store_true", help="Clear and rebuild index")

    # retrieval-status subcommand
    _ = subparsers.add_parser("retrieval-status", help="Show retrieval backend status")

    # worktree subcommand
    worktree_parser = subparsers.add_parser("worktree", help="Git worktree operations")
    _ = worktree_parser.add_argument(
        "action", choices=["detect", "create", "diff", "sync", "cleanup", "status"]
    )
    _ = worktree_parser.add_argument("slug", help="Worktree slug identifier")
    _ = worktree_parser.add_argument(
        "--plan-path", default="", dest="plan_path", help="Plan file path for hash"
    )
    _ = worktree_parser.add_argument(
        "--base-branch", default="main", dest="base_branch", help="Base branch (default: main)"
    )

    # hook subcommand
    hook_parser = subparsers.add_parser("hook", help="Run a hook module")
    _ = hook_parser.add_argument("module", help="Hook module name (e.g. context_monitor)")

    # learning subcommand
    learn_p = subparsers.add_parser("learning", help="Learning engine operations")
    learn_sub = learn_p.add_subparsers(dest="learning_action")
    al = learn_sub.add_parser("analyze", help="Run learning analysis")
    _ = al.add_argument("--since", default=None, help="Analyze since commit")
    _ = al.add_argument("--scope", default=None, help="Analysis scope")
    pl = learn_sub.add_parser("proposals", help="List pending proposals")
    _ = pl.add_argument("--max-count", type=int, default=10, dest="max_count")
    _ = pl.add_argument("--min-confidence", type=float, default=0.0, dest="min_confidence")
    dl = learn_sub.add_parser("decide", help="Decide on a proposal")
    _ = dl.add_argument("proposal_id", help="Proposal ID")
    _ = dl.add_argument("decision", choices=["accept", "reject", "ignore", "snooze"])
    _ = learn_sub.add_parser("config", help="Show learning config")
    _ = learn_sub.add_parser("status", help="Show learning status")

    # Backward compat: detect bare .jsonl arg and dispatch to analyze
    argv = sys.argv[1:]
    if argv and _is_jsonl_path(argv[0]):
        argv = ["analyze"] + argv

    args = parser.parse_args(argv)
    dispatch = {
        "analyze": _cmd_analyze,
        "init": _cmd_init,
        "doctor": _cmd_doctor,
        "serve": _cmd_serve,
        "mcp-serve": _cmd_mcp_serve,
        "reindex": _cmd_reindex,
        "retrieval-status": _cmd_retrieval_status,
        "worktree": _cmd_worktree,
        "hook": _cmd_hook,
        "learning": _cmd_learning,
    }
    command = cast(str | None, args.command)
    handler = dispatch.get(command) if command is not None else None
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)
