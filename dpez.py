#!/usr/bin/env python3
"""
dPEZ Preflight — CLI
Analyze STL files for FDM printability issues.

Usage:
    python dpez.py model.stl
    python dpez.py model.stl --printer bambu-x1c
    python dpez.py model.stl --repair --output fixed.stl
    python dpez.py model.stl --json
    python dpez.py *.stl --printer prusa-mk4
"""
import sys
import os
import glob
import click

__version__ = "0.1.0"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine  import analyze_stl
from core.models  import PrinterProfile
from reporters.terminal      import print_report, console
from reporters.json_reporter import print_json, save_json as save_json_report


def _make_output_path(filepath: str) -> str:
    """Generate a safe output path for repaired mesh, handling any extension."""
    base, ext = os.path.splitext(filepath)
    if not ext:
        ext = '.stl'
    return f"{base}_fixed{ext}"


PRINTER_MAP = {
    "bambu-x1c":   PrinterProfile.BAMBU_X1C,
    "bambu-p1s":   PrinterProfile.BAMBU_P1S,
    "bambu-p1p":   PrinterProfile.BAMBU_P1P,
    "prusa-mk4":   PrinterProfile.PRUSA_MK4,
    "prusa-mini":  PrinterProfile.PRUSA_MINI,
    "generic":     PrinterProfile.GENERIC_FDM,
}


@click.command()
@click.version_option(__version__, "--version", "-V", message="dPEZ Preflight v%(version)s")
@click.argument("files", nargs=-1, required=True)
@click.option("--printer", "-p",
              default="bambu-x1c",
              type=click.Choice(list(PRINTER_MAP.keys()), case_sensitive=False),
              show_default=True,
              help="Target printer profile")
@click.option("--repair", "-r",
              is_flag=True, default=False,
              help="Attempt automatic mesh repair")
@click.option("--fast-repair", "-F",
              is_flag=True, default=False,
              help="Fast repair: skip pymeshfix hole filling (much faster on large meshes)")
@click.option("--output", "-o",
              default=None,
              help="Output path for repaired STL (requires --repair)")
@click.option("--json", "use_json",
              is_flag=True, default=False,
              help="Output report as JSON instead of terminal display")
@click.option("--save-json", "json_output_path",
              default=None,
              help="Save JSON report to file")
def main(files, printer, repair, fast_repair, output, use_json, json_output_path):
    """
    \b
    dPEZ Preflight — STL Printability Analyzer
    Analyze STL files for FDM printing issues before you waste filament.
    """
    printer_profile = PRINTER_MAP[printer.lower()]
    
    # Expand globs (for shells that don't expand automatically)
    expanded_files = []
    for pattern in files:
        expanded = glob.glob(pattern)
        expanded_files.extend(expanded if expanded else [pattern])

    if not expanded_files:
        console.print("[red]No files found.[/red]")
        raise SystemExit(1)

    exit_code = 0

    for filepath in expanded_files:
        if not os.path.exists(filepath):
            console.print(f"[red]File not found: {filepath}[/red]")
            continue

        if not os.access(filepath, os.R_OK):
            console.print(f"[red]Permission denied: {filepath}[/red]")
            continue

        if os.path.getsize(filepath) == 0:
            console.print(f"[red]Empty file: {filepath}[/red]")
            continue

        if not filepath.lower().endswith(('.stl', '.obj', '.3mf')):
            console.print(f"[yellow]Skipping unsupported format: {filepath}[/yellow]")
            continue

        # --fast-repair implies --repair
        do_repair = repair or fast_repair

        # --- Run analysis ---
        report = analyze_stl(
            filepath=filepath,
            printer=printer_profile,
            attempt_repair=do_repair,
            fast_repair=fast_repair,
        )

        # --- Output ---
        if use_json:
            print_json(report)
        else:
            print_report(report)

        if json_output_path:
            json_path = json_output_path if len(expanded_files) == 1 else f"{filepath}.report.json"
            save_json_report(report, json_path)
            if not use_json:
                console.print(f"[dim]JSON report saved: {json_path}[/dim]")

        # --- Export repaired mesh (uses mesh already repaired during analysis) ---
        if do_repair and report.repaired_mesh is not None:
            out_path = output or _make_output_path(filepath)
            from core.repair import export_repaired
            if export_repaired(report.repaired_mesh, out_path):
                console.print(f"[green]✅ Repaired mesh exported: {out_path}[/green]")
            else:
                console.print(f"[red]❌ Failed to export repaired mesh.[/red]")

        # Track exit code: non-zero if any file has critical issues
        if report.critical_issues():
            exit_code = 1

    if len(expanded_files) > 1:
        console.print(f"\n[dim]Analyzed {len(expanded_files)} file(s)[/dim]\n")

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
