"""Tests for spreadsheet and CSV ingestion layer with German column header mapping."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
import pytest

from commercial_utility_calculator.domain.enums import Medium, UsageType
from commercial_utility_calculator.infrastructure.importers.spreadsheet_importer import (
    SpreadsheetImporter,
    ParsedPropertyData,
)


def test_import_from_csv_files(tmp_path: Path) -> None:
    # 1. Spaces CSV with German headers and comma decimals (semicolon delimited)
    spaces_csv = tmp_path / "spaces.csv"
    spaces_csv.write_text(
        "Raum_ID;Gebaeude_ID;Etage;Raumnummer;Flaeche_qm;Nutzungsart;Kostenkreis\n"
        "SP-101;Geb-A;1;101;150,50;Buero;CAMPUS;BLDG-A\n"
        "SP-102;Geb-A;2;201;200,00;Praxis;CAMPUS;BLDG-A\n",
        encoding="utf-8",
    )

    # 2. Leases CSV
    leases_csv = tmp_path / "leases.csv"
    leases_csv.write_text(
        "Vertrag_ID;Mieter_ID;Mieter_Name;Raum_ID;Mietbeginn;Mietende;USt_Option;Vorauszahlung_monatlich\n"
        "V-01;M-01;Agentur Adler;SP-101;01.01.2025;31.12.2025;Ja;500,00\n"
        "V-02;M-02;Zahnarzt Dr. Weiss;SP-102;01.01.2025;31.12.2025;Nein;600,00\n",
        encoding="utf-8",
    )

    # 3. Invoices CSV
    invoices_csv = tmp_path / "invoices.csv"
    invoices_csv.write_text(
        "Rechnungs_ID;Kostenart;Anlagen_ID;Betrag_Netto;USt_Satz;Betrag_Brutto;Zeitraum_Start;Zeitraum_Ende;Kostenkreis\n"
        "R-1;Grundsteuer;;2400,00;0,0;2400,00;01.01.2025;31.12.2025;CAMPUS\n",
        encoding="utf-8",
    )

    importer = SpreadsheetImporter()
    data = importer.import_from_csvs(
        spaces_path=str(spaces_csv),
        leases_path=str(leases_csv),
        invoices_path=str(invoices_csv),
    )

    assert len(data.spaces) == 2
    assert data.spaces[0].space_id == "SP-101"
    assert data.spaces[0].area_sqm == Decimal("150.50")
    assert data.spaces[0].usage_type == UsageType.OFFICE

    assert len(data.leases) == 2
    assert data.leases[0].tenant_name == "Agentur Adler"
    assert data.leases[0].vat_opt_in is True
    assert data.leases[1].vat_opt_in is False

    assert len(data.invoices) == 1
    assert data.invoices[0].net_amount_eur == Decimal("2400.00")


def test_import_from_excel_workbook(tmp_path: Path) -> None:
    wb_path = tmp_path / "Muster_Abrechnung.xlsx"
    wb = openpyxl.Workbook()

    # Spaces sheet
    ws_spaces = wb.active
    ws_spaces.title = "Raeume"
    ws_spaces.append(["Raum_ID", "Gebaeude_ID", "Etage", "Raumnummer", "Flaeche_qm", "Nutzungsart", "Kostenkreis"])
    ws_spaces.append(["SP-301", "Geb-C", 3, "301", 120.0, "Buero", "CAMPUS"])

    # Leases sheet
    ws_leases = wb.create_sheet(title="Mietvertraege")
    ws_leases.append(["Vertrag_ID", "Mieter_ID", "Mieter_Name", "Raum_ID", "Mietbeginn", "Mietende", "USt_Option", "Vorauszahlung_monatlich"])
    ws_leases.append(["V-301", "M-301", "Logistik Express", "SP-301", "2025-01-01", "2025-12-31", "Ja", 450.0])

    # Invoices sheet
    ws_inv = wb.create_sheet(title="Rechnungen")
    ws_inv.append(["Rechnungs_ID", "Kostenart", "Anlagen_ID", "Betrag_Netto", "USt_Satz", "Betrag_Brutto", "Zeitraum_Start", "Zeitraum_Ende", "Kostenkreis"])
    ws_inv.append(["R-301", "Hausmeister", "", 1800.0, 19.0, 2142.0, "2025-01-01", "2025-12-31", "CAMPUS"])

    wb.save(str(wb_path))

    importer = SpreadsheetImporter()
    data = importer.import_from_excel(str(wb_path))

    assert len(data.spaces) == 1
    assert data.spaces[0].space_id == "SP-301"
    assert data.spaces[0].area_sqm == Decimal("120.0")

    assert len(data.leases) == 1
    assert data.leases[0].tenant_name == "Logistik Express"

    assert len(data.invoices) == 1
    assert data.invoices[0].net_amount_eur == Decimal("1800.0")
