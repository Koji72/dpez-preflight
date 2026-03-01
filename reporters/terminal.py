"""
dPEZ Preflight — Terminal Reporter
Beautiful CLI output using Rich.
"""
import sys
import io
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text
from rich.rule import Rule
from core.models import PrintabilityReport, Severity, Issue

# Force UTF-8 output on Windows to support Unicode/emoji characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True)

SEVERITY_STYLE = {
    Severity.CRITICAL: ("❌", "bold red"),
    Severity.WARNING:  ("⚠️ ", "yellow"),
    Severity.INFO:     ("ℹ️ ", "cyan"),
    Severity.OK:       ("✅", "green"),
}

SCORE_COLOR = {
    (80, 100): "bold green",
    (50,  79): "bold yellow",
    (0,   49): "bold red",
}


def score_color(score: int) -> str:
    for (lo, hi), color in SCORE_COLOR.items():
        if lo <= score <= hi:
            return color
    return "white"


def print_report(report: PrintabilityReport) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]dPEZ Preflight — {report.filename}[/bold cyan]"))
    console.print()

    # --- Header stats ---
    stats = report.mesh_stats
    bb = stats.bounding_box or (0, 0, 0)

    info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    info_table.add_column(style="dim")
    info_table.add_column(style="white")
    info_table.add_column(style="dim")
    info_table.add_column(style="white")

    info_table.add_row("Printer",    report.printer.value,
                       "File size",  f"{report.file_size_kb:.1f} KB")
    info_table.add_row("Vertices",   f"{stats.vertex_count:,}",
                       "Faces",      f"{stats.face_count:,}")
    info_table.add_row("Dimensions", f"{bb[0]:.1f} × {bb[1]:.1f} × {bb[2]:.1f} mm",
                       "Volume",     f"{stats.volume:.2f} mm³" if stats.volume else "N/A (open mesh)")
    info_table.add_row("Watertight", "✅ Yes" if stats.is_watertight else "❌ No",
                       "Components", str(stats.component_count))

    console.print(info_table)
    console.print()

    # --- Score banner ---
    color = score_color(report.score)
    score_text = Text()
    score_text.append(f"  {report.verdict}  ", style=color)
    console.print(Panel(score_text, title="[bold]Analysis Result[/bold]", border_style=color.split()[-1]))
    console.print()

    # --- Issues ---
    if not report.issues:
        console.print("[green]No issues found.[/green]")
        return

    # Group by severity
    for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO, Severity.OK]:
        issues_in_group = [i for i in report.issues if i.severity == severity]
        if not issues_in_group:
            continue

        icon, style = SEVERITY_STYLE[severity]
        label = severity.value.upper()

        if severity == Severity.OK:
            # Compact OK list
            console.print(f"[green]Passed checks:[/green]")
            for issue in issues_in_group:
                console.print(f"  ✅ [dim]{issue.title}[/dim]")
            console.print()
            continue

        console.print(f"[{style}]{icon} {label} ({len(issues_in_group)})[/{style}]")
        console.print()

        for issue in issues_in_group:
            icon2, style2 = SEVERITY_STYLE[issue.severity]
            console.print(f"  [{style2}]{icon2} {issue.title}[/{style2}]")
            console.print(f"     [white]{issue.description}[/white]")
            
            if issue.fix_description:
                console.print(f"     [cyan]→ Fix:[/cyan] [dim]{issue.fix_description}[/dim]")
            
            if issue.auto_fixable:
                console.print(f"     [bold cyan]   [AUTO-FIXABLE][/bold cyan]")
            
            console.print()

    # --- Auto-fix summary ---
    fixable = report.auto_fixable_issues()
    if fixable:
        console.print(Panel(
            f"[bold cyan]{len(fixable)} issue(s) can be auto-repaired.[/bold cyan]\n"
            f"Run with [white]--repair[/white] flag to apply fixes and export a clean STL.",
            title="Auto-Repair Available",
            border_style="cyan"
        ))

    console.print(f"[dim]Analysis completed in {report.analysis_time_ms:.0f}ms[/dim]")
    console.print()
