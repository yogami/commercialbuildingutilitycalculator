"""End-to-end test calculating actual B.I.G. Marzahn 2025 utility statement."""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
import pytest

from commercial_utility_calculator.application.engine import CommercialUtilityEngine
from commercial_utility_calculator.infrastructure.exporters.excel_exporter import AuditReadyExcelExporter
from commercial_utility_calculator.infrastructure.importers.big_marzahn_importer import BigMarzahnImporter
from commercial_utility_calculator.infrastructure.importers.big_marzahn_portfolio_data import get_big_marzahn_2025_data


def test_calculate_big_marzahn_2025_statement_from_files() -> None:
    data_dir = Path("data/input_bka_2025")
    if not (data_dir / "Vermietete_Flächen_2025.xlsx").exists():
        pytest.skip("Local BKA 2025 raw spreadsheets not present on disk")

    importer = BigMarzahnImporter()
    data = importer.load_all_data(data_dir)

    engine = CommercialUtilityEngine()
    result = engine.calculate(
        spaces=data.spaces,
        meters=[],
        readings=[],
        leases=data.leases,
        invoices=data.invoices,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    # 1. Penny balance
    inv_sum = sum((inv.net_amount_eur for inv in data.invoices), Decimal("0.00"))
    alloc_sum = sum((line.net_amount_eur for line in result.cost_lines), Decimal("0.00"))
    assert inv_sum == alloc_sum
    assert inv_sum == Decimal("1496208.22")

    # 2. Number of tenant statements (12 commercial tenants + 1 landlord vacancy)
    assert len(result.tenant_statements) == 13

    # 3. Scansonic statement verification
    scansonic = result.tenant_statements.get("KUN0002")
    assert scansonic is not None
    assert "Scansonic" in scansonic.tenant_name
    assert scansonic.total_prepayments_eur == Decimal("340944.48")
    assert scansonic.balance_due_eur > Decimal("0.00")
    assert scansonic.recommended_new_prepayment_eur > Decimal("0.00")

    # 4. B.I.G. Tech statement (refund/Guthaben)
    big_tech = result.tenant_statements.get("KUN0001")
    assert big_tech is not None
    assert big_tech.total_prepayments_eur == Decimal("161207.88")
    assert big_tech.balance_due_eur < Decimal("0.00")  # Guthaben


def test_calculate_big_marzahn_2025_preseeded_and_excel_export() -> None:
    data = get_big_marzahn_2025_data()
    engine = CommercialUtilityEngine()
    result = engine.calculate(
        spaces=data.spaces,
        meters=[],
        readings=[],
        leases=data.leases,
        invoices=data.invoices,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    # Verify exact penny balancing
    inv_sum = sum((inv.net_amount_eur for inv in data.invoices), Decimal("0.00"))
    alloc_sum = sum((line.net_amount_eur for line in result.cost_lines), Decimal("0.00"))
    assert inv_sum == alloc_sum

    # Verify Excel Export with Gesamtabrechnung matrix and live formulas
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name

    try:
        exporter = AuditReadyExcelExporter()
        exporter.export_to_excel(result, data.spaces, tmp_path)

        wb = openpyxl.load_workbook(tmp_path, data_only=False)
        assert "Gesamtabrechnung" in wb.sheetnames
        assert "Gesamtkosten" in wb.sheetnames
        assert "Flaechen_Uebersicht" in wb.sheetnames
        assert "KUN0002_Scansonic MI GmbH" in wb.sheetnames

        ws_matrix = wb["Gesamtabrechnung"]
        # Check formula in summary row
        found_sum_formula = False
        for r in range(ws_matrix.max_row - 10, ws_matrix.max_row + 1):
            val = str(ws_matrix.cell(r, 4).value or "")
            if "=SUM(" in val:
                found_sum_formula = True
                break
        assert found_sum_formula, "Gesamtabrechnung matrix must contain live SUM formulas"

        # Check tenant sheet sections A, B, C, D
        ws_scansonic = wb["KUN0002_Scansonic MI GmbH"]
        cell_texts = [str(ws_scansonic.cell(r, 1).value or "") for r in range(1, 40)]
        assert any("(A)" in t for t in cell_texts)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
