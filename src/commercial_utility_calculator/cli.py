"""Command line interface for the commercial utility calculator."""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from commercial_utility_calculator.application.benchmark import create_spree_campus_benchmark
from commercial_utility_calculator.application.engine import CommercialUtilityEngine
from commercial_utility_calculator.infrastructure.exporters.excel_exporter import AuditReadyExcelExporter
from commercial_utility_calculator.infrastructure.importers.spreadsheet_importer import SpreadsheetImporter


def main_cli(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit-Proof German Commercial Utility Calculator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run benchmark calculation and export Excel statement")
    bench_parser.add_argument("--output", "-o", default="Gewerbehof_SpreeCampus_Abrechnung_2025.xlsx", help="Output Excel path")

    # Calculate command
    calc_parser = subparsers.add_parser("calculate", help="Run calculation on custom Excel or CSV files")
    calc_parser.add_argument("--input-excel", "-i", help="Path to input Excel workbook")
    calc_parser.add_argument("--spaces", help="Path to spaces CSV")
    calc_parser.add_argument("--leases", help="Path to leases CSV")
    calc_parser.add_argument("--invoices", help="Path to invoices CSV")
    calc_parser.add_argument("--meters", help="Path to meters CSV")
    calc_parser.add_argument("--readings", help="Path to readings CSV")
    calc_parser.add_argument("--output", "-o", default="Betriebskostenabrechnung.xlsx", help="Output Excel path")
    calc_parser.add_argument("--start-date", default="2025-01-01", help="Billing start date (YYYY-MM-DD)")
    calc_parser.add_argument("--end-date", default="2025-12-31", help="Billing end date (YYYY-MM-DD)")

    # Templates command
    tpl_parser = subparsers.add_parser("generate-templates", help="Generate blank CSV and Excel templates")
    tpl_parser.add_argument("--output-dir", "-d", default="templates", help="Output directory for templates")

    parsed = parser.parse_args(args)

    if parsed.command == "benchmark":
        return _run_benchmark(parsed.output)
    if parsed.command == "calculate":
        return _run_calculate(parsed)
    if parsed.command == "generate-templates":
        return _run_generate_templates(parsed.output_dir)
    return 0


def _run_benchmark(output_path: str) -> int:
    data = create_spree_campus_benchmark()
    engine = CommercialUtilityEngine()
    result = engine.calculate(
        spaces=data.spaces,
        meters=data.meters,
        readings=data.readings,
        leases=data.leases,
        invoices=data.invoices,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )
    exporter = AuditReadyExcelExporter()
    exporter.export_to_excel(result, data.spaces, output_path)
    print(f"Successfully generated benchmark statement at: {output_path}")
    return 0


def _run_calculate(args: argparse.Namespace) -> int:
    importer = SpreadsheetImporter()
    if args.input_excel:
        data = importer.import_from_excel(args.input_excel)
    else:
        data = importer.import_from_csvs(
            spaces_path=args.spaces,
            leases_path=args.leases,
            invoices_path=args.invoices,
            meters_path=args.meters,
            readings_path=args.readings,
        )

    b_start = date.fromisoformat(args.start_date)
    b_end = date.fromisoformat(args.end_date)

    engine = CommercialUtilityEngine()
    result = engine.calculate(
        spaces=data.spaces,
        meters=data.meters,
        readings=data.readings,
        leases=data.leases,
        invoices=data.invoices,
        billing_start=b_start,
        billing_end=b_end,
    )
    exporter = AuditReadyExcelExporter()
    exporter.export_to_excel(result, data.spaces, args.output)
    print(f"Successfully calculated and exported statement to: {args.output}")
    return 0


def _run_generate_templates(output_dir: str) -> int:
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)

    spaces_csv = p / "raeume_template.csv"
    spaces_csv.write_text(
        "Raum_ID;Gebaeude_ID;Etage;Raumnummer;Flaeche_qm;Nutzungsart;Kostenkreis\n"
        "SP-101;Geb-A;1;101;250,00;Buero;CAMPUS;BLDG-A\n"
        "SP-201;Geb-A;2;201;300,00;Praxis;CAMPUS;BLDG-A\n",
        encoding="utf-8",
    )

    leases_csv = p / "mietvertraege_template.csv"
    leases_csv.write_text(
        "Vertrag_ID;Mieter_ID;Mieter_Name;Raum_ID;Mietbeginn;Mietende;USt_Option;Vorauszahlung_monatlich\n"
        "V-001;M-001;Musterfirma GmbH;SP-101;2025-01-01;2025-12-31;Ja;500,00\n"
        "V-002;M-002;Dr. med. Beispiel;SP-201;2025-01-01;2025-12-31;Nein;600,00\n",
        encoding="utf-8",
    )

    invoices_csv = p / "rechnungen_template.csv"
    invoices_csv.write_text(
        "Rechnungs_ID;Kostenart;Anlagen_ID;Betrag_Netto;USt_Satz;Betrag_Brutto;Zeitraum_Start;Zeitraum_Ende;Kostenkreis\n"
        "R-001;Grundsteuer;;3600,00;0,0;3600,00;2025-01-01;2025-12-31;CAMPUS\n"
        "R-002;Hausmeister;;4800,00;19,0;5712,00;2025-01-01;2025-12-31;CAMPUS\n",
        encoding="utf-8",
    )

    print(f"Generated CSV templates in {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
