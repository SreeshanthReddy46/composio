import argparse
import asyncio
import json
import sys
from pathlib import Path
import yaml
from rich.console import Console
from rich.syntax import Syntax

from src.research.schema import AppInput, AppRecord
from src.research.pipeline import ResearchPipeline

console = Console()

DEFAULT_KNOWN_APPS = {
    "notion": AppInput(id="notion", name="Notion", category="Productivity & Collaboration", hint_url="https://developers.notion.com"),
    "slack": AppInput(id="slack", name="Slack", category="Productivity & Collaboration", hint_url="https://api.slack.com"),
    "github": AppInput(id="github", name="GitHub", category="Developer Tools & Cloud", hint_url="https://docs.github.com/en/rest"),
}


def load_apps_from_yaml(yaml_path: Path) -> list[AppInput]:
    if not yaml_path.exists():
        return list(DEFAULT_KNOWN_APPS.values())
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return list(DEFAULT_KNOWN_APPS.values())
    apps = []
    for item in data:
        apps.append(AppInput(**item))
    return apps


def main():
    parser = argparse.ArgumentParser(
        prog="research",
        description="Composio 100-App Toolkit-Buildability Research Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run research pipeline across apps")
    run_parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("apps.yaml"),
        help="Path to apps.yaml file",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to output jsonl file (defaults to data/pass1.jsonl for v1, data/pass2.jsonl for v2)",
    )
    run_parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default="v2",
        choices=["v1", "v2"],
        help="Pipeline execution mode (v1: naive baseline, v2: verified)",
    )
    run_parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=10,
        help="Concurrency limit for HTTP requests",
    )
    run_parser.add_argument(
        "--all",
        action="store_true",
        help="Run across all apps in apps.yaml",
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume execution skipping already processed apps (default: True)",
    )
    run_parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Overwrite and restart execution from scratch",
    )
    run_parser.add_argument(
        "--lock",
        action="store_true",
        help="Freeze output file as read-only and generate .sha256 checksum upon completion",
    )
    run_parser.add_argument(
        "--review-queue",
        type=Path,
        default=Path("data/review_queue.csv"),
        help="Path to output review_queue.csv",
    )
    run_parser.add_argument(
        "--app",
        type=str,
        help="Single app name or ID to research (e.g. Notion, Slack)",
    )
    run_parser.add_argument(
        "--app-id",
        type=str,
        help="Single app ID to research (alias for --app)",
    )

    # Check command
    check_parser = subparsers.add_parser("check", help="Run checks on an output jsonl dataset")
    check_parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to jsonl file to check",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        # Resolve output path if not specified
        if args.output is None:
            args.output = Path("data/pass2.jsonl") if args.mode == "v2" else Path("data/pass1.jsonl")

        target_app = args.app or args.app_id
        if target_app:
            target_key = target_app.strip().lower()
            all_apps = load_apps_from_yaml(args.input)
            matched = [a for a in all_apps if a.id.lower() == target_key or a.name.lower() == target_key]
            if matched:
                apps = matched
            elif target_key in DEFAULT_KNOWN_APPS:
                apps = [DEFAULT_KNOWN_APPS[target_key]]
            else:
                apps = [AppInput(id=target_key, name=target_app, hint_url=f"https://developers.{target_key}.com")]
        else:
            apps = load_apps_from_yaml(args.input)

        pipeline = ResearchPipeline(
            concurrency=args.concurrency,
            mode=args.mode,
            review_queue_path=args.review_queue,
        )
        results = asyncio.run(
            pipeline.run(
                apps,
                output_path=args.output,
                resume=args.resume,
                lock_when_done=args.lock or args.all,
            )
        )
        
        console.print(f"[bold green]Batch Complete! {len(results)} total records in {args.output}[/bold green]")
        
        if target_app and results:
            target_record = next((r for r in results if r.id.lower() == target_key), results[-1])
            formatted_json = json.dumps(target_record.model_dump(), indent=2)
            syntax = Syntax(formatted_json, "json", theme="monokai", line_numbers=True)
            console.print(syntax)

    elif args.command == "check":
        console.print(f"[yellow]Checking {args.input}...[/yellow]")


if __name__ == "__main__":
    main()
