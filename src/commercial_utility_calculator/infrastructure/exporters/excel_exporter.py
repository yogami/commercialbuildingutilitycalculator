"""Audit-ready Excel workbook generator retaining live Excel formulas (Prüffähigkeit)."""

from decimal import Decimal
from typing import Dict, List, Tuple
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from commercial_utility_calculator.domain.entities import PhysicalSpace
from commercial_utility_calculator.application.engine import EngineCalculationResult, TenantStatement
from commercial_utility_calculator.application.services.cost_circle_allocator import CostAllocationLine


class AuditReadyExcelExporter:
    """Exports utility statements with live formulas so auditors can verify calculations."""

    HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    SECTION_FONT = Font(name="Calibri", size=12, bold=True, color="1F497D")
    HEADER_FILL = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    BOLD_FONT = Font(name="Calibri", size=11, bold=True)
    REGULAR_FONT = Font(name="Calibri", size=11)
    MONEY_FORMAT = '#,##0.00 €'
    AREA_DAYS_FORMAT = '#,##0.00'
    PERCENT_FORMAT = '0.0000%'

    def export_to_excel(
        self,
        result: EngineCalculationResult,
        spaces: List[PhysicalSpace],
        output_filepath: str,
    ) -> None:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default blank sheet

        self._create_gesamtabrechnung_matrix_sheet(wb, result)
        self._create_costs_sheet(wb, result)
        self._create_area_overview_sheet(wb, result, spaces)

        for tenant_id, statement in sorted(result.tenant_statements.items()):
            self._create_tenant_sheet(wb, statement, result, spaces)

        wb.save(output_filepath)

    def _create_gesamtabrechnung_matrix_sheet(
        self, wb: openpyxl.Workbook, result: EngineCalculationResult
    ) -> None:
        ws = wb.create_sheet(title="Gesamtabrechnung")
        ws.cell(1, 1, f"Gesamtabrechnung der Betriebskosten {result.billing_start.year}").font = Font(
            name="Calibri", size=14, bold=True
        )
        ws.cell(
            2,
            1,
            f"Abrechnungszeitraum: {result.billing_start.strftime('%d.%m.%Y')} - {result.billing_end.strftime('%d.%m.%Y')}",
        ).font = self.REGULAR_FONT

        tenant_ids = sorted(result.tenant_statements.keys())
        fixed_headers = [
            "Rechnungs-ID",
            "Kostenart / Kategorie",
            "Scope / Verteiler",
            "Gesamtkosten (Netto)",
        ]
        tenant_headers = [
            f"{result.tenant_statements[tid].tenant_name[:20]} ({tid})"
            for tid in tenant_ids
        ]
        headers = fixed_headers + tenant_headers
        start_row = 4
        for c_idx, h in enumerate(headers, start=1):
            cell = ws.cell(start_row, c_idx, h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")

        line_map: Dict[Tuple[str, str], CostAllocationLine] = {}
        for l in result.cost_lines:
            line_map[(l.invoice_id, l.tenant_id)] = l

        cur_row = start_row + 1
        for inv in result.invoices:
            row_data = [
                inv.invoice_id,
                inv.cost_category,
                inv.cost_circle_scope,
                float(inv.net_amount_eur),
            ]
            for tid in tenant_ids:
                line = line_map.get((inv.invoice_id, tid))
                amt = float(line.net_amount_eur) if line else 0.0
                row_data.append(amt)
            ws.append(row_data)

            ws.cell(cur_row, 4).number_format = self.MONEY_FORMAT
            for c_offset in range(len(tenant_ids)):
                ws.cell(cur_row, 5 + c_offset).number_format = self.MONEY_FORMAT
            cur_row += 1

        # Summary rows
        r = cur_row + 1
        ws.cell(r, 2, "Summe Netto:").font = self.BOLD_FONT
        ws.cell(r, 4, f"=SUM(D{start_row + 1}:D{cur_row - 1})").font = self.BOLD_FONT
        ws.cell(r, 4).number_format = self.MONEY_FORMAT
        for c_idx, tid in enumerate(tenant_ids, start=5):
            col_letter = get_column_letter(c_idx)
            cell = ws.cell(r, c_idx, f"=SUM({col_letter}{start_row + 1}:{col_letter}{cur_row - 1})")
            cell.font = self.BOLD_FONT
            cell.number_format = self.MONEY_FORMAT
            cell.fill = self.TOTAL_FILL

        r += 1
        ws.cell(r, 2, "Summe Abrechnungsbetrag (inkl. MwSt):").font = self.BOLD_FONT
        for c_idx, tid in enumerate(tenant_ids, start=5):
            st = result.tenant_statements[tid]
            billed = st.total_net_eur + st.total_vat_eur if st.vat_opt_in else st.total_gross_eur
            cell = ws.cell(r, c_idx, float(billed))
            cell.font = self.BOLD_FONT
            cell.number_format = self.MONEY_FORMAT

        r += 1
        ws.cell(r, 2, "Geleistete Vorauszahlungen:").font = self.BOLD_FONT
        for c_idx, tid in enumerate(tenant_ids, start=5):
            st = result.tenant_statements[tid]
            cell = ws.cell(r, c_idx, float(st.total_prepayments_eur))
            cell.font = self.BOLD_FONT
            cell.number_format = self.MONEY_FORMAT

        r += 1
        ws.cell(r, 2, "Abrechnungssaldo (Nachzahlung / -Guthaben):").font = Font(
            name="Calibri", size=11, bold=True, color="9C0006"
        )
        for c_idx, tid in enumerate(tenant_ids, start=5):
            col_letter = get_column_letter(c_idx)
            cell = ws.cell(r, c_idx, f"={col_letter}{r - 2}-{col_letter}{r - 1}")
            cell.font = Font(name="Calibri", size=11, bold=True, color="9C0006")
            cell.number_format = self.MONEY_FORMAT
            cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        r += 1
        ws.cell(r, 2, "Neue monatl. Vorauszahlung ab Folgejahr (§ 560 BGB):").font = Font(
            name="Calibri", size=11, bold=True, color="1F497D"
        )
        for c_idx, tid in enumerate(tenant_ids, start=5):
            col_letter = get_column_letter(c_idx)
            cell = ws.cell(r, c_idx, f"=ROUND({col_letter}{r - 3}/12, 0)")
            cell.font = Font(name="Calibri", size=11, bold=True, color="1F497D")
            cell.number_format = self.MONEY_FORMAT
            cell.fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")

        self._auto_fit_columns(ws)

    def _create_costs_sheet(self, wb: openpyxl.Workbook, result: EngineCalculationResult) -> None:
        ws = wb.create_sheet(title="Gesamtkosten")
        headers = [
            "Rechnungs-ID",
            "Kostenkategorie",
            "Kostenkreis / Scope",
            "Leistungszeitraum Start",
            "Leistungszeitraum Ende",
            "Nettobetrag",
            "USt-Satz",
            "Bruttobetrag",
        ]
        ws.append(headers)
        self._format_header_row(ws, len(headers))

        for inv in result.invoices:
            ws.append([
                inv.invoice_id,
                inv.cost_category,
                inv.cost_circle_scope,
                inv.billing_start.isoformat(),
                inv.billing_end.isoformat(),
                float(inv.net_amount_eur),
                float(inv.vat_rate_percent / Decimal("100.0")),
                float(inv.gross_amount_eur),
            ])
            cur_row = ws.max_row
            ws.cell(cur_row, 6).number_format = self.MONEY_FORMAT
            ws.cell(cur_row, 7).number_format = '0.0%'
            ws.cell(cur_row, 8).number_format = self.MONEY_FORMAT

        total_row = ws.max_row + 1
        ws.cell(total_row, 2, "Gesamtsumme").font = self.BOLD_FONT
        ws.cell(total_row, 6, f"=SUM(F2:F{total_row - 1})").font = self.BOLD_FONT
        ws.cell(total_row, 6).number_format = self.MONEY_FORMAT
        ws.cell(total_row, 8, f"=SUM(H2:H{total_row - 1})").font = self.BOLD_FONT
        ws.cell(total_row, 8).number_format = self.MONEY_FORMAT
        self._auto_fit_columns(ws)

    def _create_area_overview_sheet(
        self, wb: openpyxl.Workbook, result: EngineCalculationResult, spaces: List[PhysicalSpace]
    ) -> None:
        ws = wb.create_sheet(title="Flaechen_Uebersicht")
        headers = [
            "Raum-ID",
            "Gebaeude",
            "Etage",
            "Flaeche (m²)",
            "Nutzer / Mieter",
            "Von",
            "Bis",
            "Tage",
            "m²-Tage",
            "Status",
        ]
        ws.append(headers)
        self._format_header_row(ws, len(headers))

        space_lookup = {s.space_id: s for s in spaces}
        for s in result.area_result.slices:
            sp = space_lookup.get(s.space_id)
            bldg = sp.building_id if sp else ""
            floor = sp.floor if sp else 0
            status = "Leerstand" if s.is_vacancy else "Vermietet"
            ws.append([
                s.space_id,
                bldg,
                floor,
                float(s.area_sqm),
                s.tenant_name,
                s.start_date.isoformat(),
                s.end_date.isoformat(),
                s.days,
                float(s.sqm_days),
                status,
            ])
            r = ws.max_row
            ws.cell(r, 4).number_format = '#,##0.00 "m²"'
            ws.cell(r, 9).number_format = self.AREA_DAYS_FORMAT

        total_row = ws.max_row + 1
        ws.cell(total_row, 5, "Summe m²-Tage").font = self.BOLD_FONT
        ws.cell(total_row, 9, f"=SUM(I2:I{total_row - 1})").font = self.BOLD_FONT
        ws.cell(total_row, 9).number_format = self.AREA_DAYS_FORMAT
        self._auto_fit_columns(ws)

    def _create_tenant_sheet(
        self,
        wb: openpyxl.Workbook,
        statement: TenantStatement,
        result: EngineCalculationResult,
        spaces: List[PhysicalSpace],
    ) -> None:
        raw_name = f"{statement.tenant_id}_{statement.tenant_name}"
        clean_title = raw_name.replace("/", "_").replace("\\", "_")[:31]
        ws = wb.create_sheet(title=clean_title)

        ws.cell(1, 1, f"Betriebskostenabrechnung {result.billing_start.year}").font = Font(
            name="Calibri", size=14, bold=True
        )
        ws.cell(2, 1, f"Mieter: {statement.tenant_name} (Debitor: {statement.tenant_id})").font = self.BOLD_FONT
        addr_line = f"{statement.street_address or ''}, {statement.postal_code or ''} {statement.city or ''}".strip(", ")
        if addr_line:
            ws.cell(3, 1, f"Adresse: {addr_line}").font = self.REGULAR_FONT
        tax_label = "Optiert (§ 9 UStG, 19% MwSt)" if statement.vat_opt_in else "Befreit (Bruttoabrechnung)"
        ws.cell(4, 1, f"USt-Status: {tax_label}").font = self.REGULAR_FONT

        # Section (A)
        ws.cell(6, 1, "(A) Aufstellung / Berechnung der Gesamtkosten & Mieteranteil").font = self.SECTION_FONT

        headers = [
            "Kostenart",
            "Kostenkreis",
            "Eigene m²-Tage",
            "Gesamt m²-Tage",
            "Umlageanteil",
            "Rechnung Netto",
            "Anteil Netto",
            "USt-Satz",
            "USt-Betrag",
            "Abrechnungsbetrag",
        ]
        start_row = 7
        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(start_row, col_idx, h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL

        cur_row = start_row + 1
        for line in statement.cost_lines:
            ws.append([
                line.cost_category,
                line.cost_circle_scope,
                float(line.numerator_sqm_days),
                float(line.denominator_sqm_days),
                f"=C{cur_row}/D{cur_row}",
                float(line.net_amount_eur / line.cost_ratio if line.cost_ratio > Decimal("0") else Decimal("0.0")),
                f"=F{cur_row}*E{cur_row}",
                float(line.vat_rate_percent / Decimal("100.0")),
                f"=G{cur_row}*H{cur_row}" if line.vat_opt_in else 0.0,
                f"=G{cur_row}+I{cur_row}" if line.vat_opt_in else f"=G{cur_row}",
            ])
            ws.cell(cur_row, 3).number_format = self.AREA_DAYS_FORMAT
            ws.cell(cur_row, 4).number_format = self.AREA_DAYS_FORMAT
            ws.cell(cur_row, 5).number_format = self.PERCENT_FORMAT
            ws.cell(cur_row, 6).number_format = self.MONEY_FORMAT
            ws.cell(cur_row, 7).number_format = self.MONEY_FORMAT
            ws.cell(cur_row, 8).number_format = '0.0%'
            ws.cell(cur_row, 9).number_format = self.MONEY_FORMAT
            ws.cell(cur_row, 10).number_format = self.MONEY_FORMAT
            cur_row += 1

        last_data_row = cur_row - 1
        r = last_data_row + 2
        ws.cell(r, 6, "Summe Netto:").font = self.BOLD_FONT
        ws.cell(r, 7, f"=SUM(G{start_row + 1}:G{last_data_row})").font = self.BOLD_FONT
        ws.cell(r, 7).number_format = self.MONEY_FORMAT

        r += 1
        ws.cell(r, 6, "Summe MwSt:").font = self.BOLD_FONT
        ws.cell(r, 9, f"=SUM(I{start_row + 1}:I{last_data_row})").font = self.BOLD_FONT
        ws.cell(r, 9).number_format = self.MONEY_FORMAT

        r += 1
        ws.cell(r, 6, "Gesamtabrechnungsbetrag:").font = self.BOLD_FONT
        ws.cell(r, 10, f"=SUM(J{start_row + 1}:J{last_data_row})").font = self.BOLD_FONT
        ws.cell(r, 10).number_format = self.MONEY_FORMAT
        ws.cell(r, 10).fill = self.TOTAL_FILL

        r += 1
        ws.cell(r, 6, "Geleistete Vorauszahlungen:").font = self.BOLD_FONT
        ws.cell(r, 10, float(statement.total_prepayments_eur)).font = self.BOLD_FONT
        ws.cell(r, 10).number_format = self.MONEY_FORMAT

        r += 1
        ws.cell(r, 6, "Abrechnungssaldo (Nachzahlung / -Guthaben):").font = Font(
            name="Calibri", size=12, bold=True, color="9C0006"
        )
        ws.cell(r, 10, f"=J{r - 2}-J{r - 1}").font = Font(name="Calibri", size=12, bold=True, color="9C0006")
        ws.cell(r, 10).number_format = self.MONEY_FORMAT
        ws.cell(r, 10).fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        # Section (B)
        r += 3
        ws.cell(r, 1, "(B) Änderung der monatlichen Vorauszahlung nach § 560 Abs. 4 BGB").font = self.SECTION_FONT
        r += 1
        ws.cell(
            r,
            1,
            "Aufgrund des Abrechnungsergebnisses und der veränderten Kostenstruktur wird die monatliche Vorauszahlung wie folgt angepasst:",
        ).font = self.REGULAR_FONT
        r += 1
        cur_monthly_vz = (statement.total_prepayments_eur / Decimal("12.0")).quantize(Decimal("0.01"))
        ws.cell(r, 2, "Bisherige monatl. Vorauszahlung:")
        ws.cell(r, 4, float(cur_monthly_vz)).number_format = self.MONEY_FORMAT
        r += 1
        ws.cell(r, 2, "Neue empfohlene monatl. Vorauszahlung ab Folgejahr:")
        ws.cell(r, 4, float(statement.recommended_new_prepayment_eur)).number_format = self.MONEY_FORMAT
        ws.cell(r, 4).font = self.BOLD_FONT
        ws.cell(r, 4).fill = self.TOTAL_FILL

        # Section (C)
        r += 3
        ws.cell(r, 1, "(C) Erläuterung der Umlageschlüssel").font = self.SECTION_FONT
        r += 1
        key_explanations = [
            ("CAMPUS (Liegenschaft)", "Umlage nach Fläche × Nutzungstage über die gesamte Liegenschaft"),
            ("Haus 1+2 / Haus 1-3 / Haus 4 / Haus 5", "Gebäudeweise Umlage für Aufzug, Fernwärme, Wasser oder Technik"),
            ("Direktzähler / Mieter direkt", "Direkte Zuordnung von Strom/Wartung nach geeichten Zählern gem. Mietvertrag"),
        ]
        for key_name, key_desc in key_explanations:
            ws.cell(r, 2, key_name).font = self.BOLD_FONT
            ws.cell(r, 5, key_desc).font = self.REGULAR_FONT
            r += 1

        # Section (D)
        r += 2
        ws.cell(r, 1, "(D) Nutzungszeitraum und Anteile je Mieteinheit").font = self.SECTION_FONT
        r += 1
        d_headers = ["Raum / Einheit", "Fläche (m²)", "Nutzung von", "Nutzung bis", "Tage", "m²-Tage"]
        for c_idx, dh in enumerate(d_headers, start=2):
            cell = ws.cell(r, c_idx, dh)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL

        r += 1
        for sl in statement.occupancy_slices:
            ws.cell(r, 2, sl.space_id)
            ws.cell(r, 3, float(sl.area_sqm)).number_format = '#,##0.00 "m²"'
            ws.cell(r, 4, sl.start_date.strftime("%d.%m.%Y"))
            ws.cell(r, 5, sl.end_date.strftime("%d.%m.%Y"))
            ws.cell(r, 6, sl.days)
            ws.cell(r, 7, float(sl.sqm_days)).number_format = self.AREA_DAYS_FORMAT
            r += 1

        self._auto_fit_columns(ws)

    def _format_header_row(self, ws: openpyxl.worksheet.worksheet.Worksheet, col_count: int) -> None:
        for c in range(1, col_count + 1):
            cell = ws.cell(1, c)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def _auto_fit_columns(self, ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if val.startswith("="):
                    val = "123,456.78 €"
                max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
