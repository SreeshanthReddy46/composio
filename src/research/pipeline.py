import asyncio
import csv
import hashlib
import json
import logging
import os
import stat
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from tenacity import retry, stop_after_attempt, wait_exponential

from src.research.schema import AppInput, AppRecord, EvidenceField
from src.research.collector import Collector
from src.research.extractor import Extractor
from src.research.verifier import Verifier
from src.research.checks import run_deterministic_checks

logger = logging.getLogger(__name__)
console = Console()


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def make_file_readonly(file_path: Path) -> None:
    """Make file read-only on Windows / POSIX."""
    try:
        mode = os.stat(file_path).st_mode
        os.chmod(file_path, mode & ~stat.S_IWRITE)
        if os.name == "nt":
            os.system(f'attrib +r "{file_path}"')
    except Exception as e:
        logger.warning(f"Could not set read-only attribute: {e}")


def print_cost_and_time_estimate(apps_count: int, concurrency: int = 10, mode: str = "v1") -> None:
    """Display up-front estimates for duration, API calls, and model token costs."""
    avg_latency = 1.2 if mode == "v1" else 2.5
    est_seconds = max(2.0, (apps_count * avg_latency) / max(1, concurrency))
    est_minutes = est_seconds / 60.0

    in_multiplier = 2500 if mode == "v1" else 6500
    out_multiplier = 450 if mode == "v1" else 900
    est_input_tokens = apps_count * in_multiplier
    est_output_tokens = apps_count * out_multiplier
    est_cost_usd = (est_input_tokens * 0.075 / 1_000_000) + (est_output_tokens * 0.30 / 1_000_000)

    table = Table(title=f"Batch Run Pre-Flight Estimate (Mode: {mode.upper()})", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold green")

    table.add_row("Total Apps to Process", str(apps_count))
    table.add_row("Execution Mode", mode.upper())
    table.add_row("Worker Concurrency", str(concurrency))
    table.add_row("Estimated Wall Time", f"~{est_seconds:.1f}s ({est_minutes:.1f} min)")
    table.add_row("Estimated Input Tokens", f"~{est_input_tokens:,}")
    table.add_row("Estimated Output Tokens", f"~{est_output_tokens:,}")
    table.add_row("Estimated LLM Cost (USD)", f"${est_cost_usd:.4f}")

    console.print(Panel(table, title="[bold cyan]Composio Research Agent Execution[/bold cyan]", expand=False))


class ResearchPipeline:
    def __init__(
        self,
        concurrency: int = 10,
        mode: str = "v1",
        review_queue_path: Path = Path("data/review_queue.csv"),
    ):
        self.concurrency = concurrency
        self.mode = mode
        self.review_queue_path = review_queue_path
        self.semaphore = asyncio.Semaphore(concurrency)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=False)
    async def process_app(
        self,
        app: AppInput,
        collector: Collector,
        extractor: Extractor,
        verifier: Verifier,
    ) -> Tuple[AppRecord, List[Dict[str, str]]]:
        async with self.semaphore:
            if self.mode == "v1":
                # Naive baseline
                sources = await collector.collect_sources_for_app(app)
                record = await extractor.extract_v1(app, sources)
                return record, []

            # Mode v2: Verified Architecture
            # 1. Multi-surface collection
            sources = await collector.collect_sources_for_app(app)
            mcp_info = collector.check_mcp_registry(app.id)
            in_composio = collector.check_composio_catalog(app.id)

            # 2. Strict Extractor
            record = await extractor.extract_v2(app, sources, mcp_info, in_composio)

            # 3. Deterministic checks (URLs alive, quotes in page, enums valid, confidence lowered on fail)
            record, deterministic_failures = run_deterministic_checks(record, sources)

            # 4. Independent Verifier model
            verifications = await verifier.verify_record(record, sources)

            # 5. Gather disagreements & check failures for review queue
            review_items: List[Dict[str, str]] = []

            # Deterministic check failures
            for field_name, err in deterministic_failures:
                field_obj: EvidenceField = getattr(record, field_name)
                review_items.append({
                    "app": app.id,
                    "field": field_name,
                    "extractor_answer": str(field_obj.value),
                    "verifier_answer": f"CHECK FAILED: {err}",
                    "url": field_obj.evidence_url or (app.hint_url or ""),
                })

            # Verifier model disagreements
            for field_name, v_res in verifications.items():
                if not v_res.get("agree", True):
                    field_obj: EvidenceField = getattr(record, field_name)
                    review_items.append({
                        "app": app.id,
                        "field": field_name,
                        "extractor_answer": str(field_obj.value),
                        "verifier_answer": str(v_res.get("verifier_answer")),
                        "url": field_obj.evidence_url or (app.hint_url or ""),
                    })

            return record, review_items

    async def run(
        self,
        apps: List[AppInput],
        output_path: Path,
        resume: bool = True,
        lock_when_done: bool = False,
    ) -> List[AppRecord]:
        processed_ids = set()
        existing_records = []

        if resume and output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            processed_ids.add(data["id"])
                            existing_records.append(AppRecord.model_validate(data))
            except Exception as e:
                logger.warning(f"Error reading existing output for resume: {e}")

        apps_to_process = [app for app in apps if app.id not in processed_ids]

        # Print cost and time estimates upfront
        print_cost_and_time_estimate(len(apps_to_process), concurrency=self.concurrency, mode=self.mode)

        if not apps_to_process:
            console.print("[yellow]All apps already processed in existing output! Nothing to run.[/yellow]")
            return existing_records

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_queue_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            try:
                os.chmod(output_path, stat.S_IWRITE | stat.S_IREAD)
                if os.name == "nt":
                    os.system(f'attrib -r "{output_path}"')
            except Exception:
                pass

        out_mode = "a" if resume and output_path.exists() else "w"
        results = list(existing_records)

        # Initialize review queue CSV header if needed
        write_rq_header = not self.review_queue_path.exists() or os.path.getsize(self.review_queue_path) == 0
        rq_file = open(self.review_queue_path, "a", newline="", encoding="utf-8")
        rq_writer = csv.DictWriter(
            rq_file,
            fieldnames=["app", "field", "extractor_answer", "verifier_answer", "url"],
        )
        if write_rq_header:
            rq_writer.writeheader()

        total_review_items = 0

        try:
            async with httpx.AsyncClient() as client:
                collector = Collector(client)
                extractor = Extractor()
                verifier = Verifier()

                with open(output_path, out_mode, encoding="utf-8") as out_file:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TextColumn("({task.completed}/{task.total})"),
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                    ) as progress:
                        task = progress.add_task(f"Researching apps (mode: {self.mode})...", total=len(apps_to_process))

                        tasks = [
                            self.process_app(app, collector, extractor, verifier)
                            for app in apps_to_process
                        ]

                        for coro in asyncio.as_completed(tasks):
                            record, review_items = await coro
                            results.append(record)
                            out_file.write(record.model_dump_json() + "\n")
                            out_file.flush()

                            if review_items:
                                rq_writer.writerows(review_items)
                                rq_file.flush()
                                total_review_items += len(review_items)

                            progress.advance(task)
        finally:
            rq_file.close()

        if total_review_items > 0:
            console.print(f"[yellow]Logged {total_review_items} disagreements/failures to {self.review_queue_path}[/yellow]")

        if lock_when_done and output_path.exists():
            checksum = compute_sha256(output_path)
            checksum_path = output_path.with_suffix(".sha256")
            with open(checksum_path, "w", encoding="utf-8") as cs_f:
                cs_f.write(f"{checksum}  {output_path.name}\n")
            
            make_file_readonly(output_path)
            console.print(f"[bold cyan]Locked {output_path} (read-only). Checksum saved to {checksum_path}[/bold cyan]")
            console.print(f"[dim]SHA-256: {checksum}[/dim]")

        return results
