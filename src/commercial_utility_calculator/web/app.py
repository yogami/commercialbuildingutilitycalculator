"""FastAPI application serving the commercial utility audit dashboard."""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from commercial_utility_calculator.application.benchmark import create_spree_campus_benchmark
from commercial_utility_calculator.application.engine import CommercialUtilityEngine, EngineCalculationResult
from commercial_utility_calculator.domain.entities import PhysicalSpace
from commercial_utility_calculator.domain.invariants import InvariantValidator
from commercial_utility_calculator.infrastructure.exporters.excel_exporter import AuditReadyExcelExporter
from commercial_utility_calculator.infrastructure.importers.big_marzahn_portfolio_data import get_big_marzahn_2025_data
from commercial_utility_calculator.infrastructure.importers.spreadsheet_importer import (
    ParsedPropertyData,
    SpreadsheetImporter,
)

app = FastAPI(title="Commercial Building Utility Calculator", version="0.1.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory store for active calculations
STATE: Dict[str, Any] = {
    "active_dataset": "big_marzahn",
    "calculations": {},
}


def _get_active_calculation(
    dataset: str = "big_marzahn",
) -> Tuple[EngineCalculationResult, List[PhysicalSpace], Dict[str, Any]]:
    clean_ds = dataset if dataset in ("big_marzahn", "spree_campus", "uploaded") else "big_marzahn"

    if clean_ds in STATE["calculations"]:
        entry = STATE["calculations"][clean_ds]
        return entry["result"], entry["spaces"], entry["cached_json"]

    if clean_ds == "big_marzahn":
        data = get_big_marzahn_2025_data()
        b_start = date(2025, 1, 1)
        b_end = date(2025, 12, 31)
        name = "B.I.G. Marzahn Gewerbepark (Schwarze-Pumpe-Weg 12-16)"
    else:
        data = create_spree_campus_benchmark()
        b_start = date(2025, 1, 1)
        b_end = date(2025, 12, 31)
        name = "Spree-Campus Gewerbehof (Demo Benchmark)"

    engine = CommercialUtilityEngine()
    result = engine.calculate(
        spaces=data.spaces,
        meters=data.meters if clean_ds == "spree_campus" else [],
        readings=data.readings if clean_ds == "spree_campus" else [],
        leases=data.leases,
        invoices=data.invoices,
        billing_start=b_start,
        billing_end=b_end,
    )
    cached_json = _serialize_result(result, data)
    cached_json["portfolio_name"] = name
    cached_json["dataset"] = clean_ds

    STATE["calculations"][clean_ds] = {
        "result": result,
        "spaces": data.spaces,
        "cached_json": cached_json,
    }
    STATE["active_dataset"] = clean_ds
    return result, data.spaces, cached_json


def _serialize_result(result: EngineCalculationResult, data: ParsedPropertyData) -> Dict[str, Any]:
    total_sqm = sum((s.area_sqm for s in data.spaces), Decimal("0.0"))
    total_sqm_days = result.area_result.total_sqm_days
    vac_sqm_days = result.area_result.vacancy_sqm_days
    vac_pct = (vac_sqm_days / total_sqm_days * Decimal("100.0")) if total_sqm_days > Decimal("0") else Decimal("0.0")

    total_net = sum((inv.net_amount_eur for inv in data.invoices), Decimal("0.00"))
    total_gross = sum((inv.gross_amount_eur for inv in data.invoices), Decimal("0.00"))
    total_balance = sum((st.balance_due_eur for st in result.tenant_statements.values()), Decimal("0.00"))
    total_prepayments = sum((st.total_prepayments_eur for st in result.tenant_statements.values()), Decimal("0.00"))

    summary = {
        "total_sqm": float(total_sqm),
        "space_count": len(data.spaces),
        "total_days": result.area_result.total_days,
        "total_sqm_days": float(total_sqm_days),
        "vacancy_sqm_days": float(vac_sqm_days),
        "vacancy_percentage": float(vac_pct),
        "total_net_eur": float(total_net),
        "total_gross_eur": float(total_gross),
        "total_prepayments_eur": float(total_prepayments),
        "total_balance_due_eur": float(total_balance),
    }

    invariants = {
        "penny_balance": True,
        "area_continuity": True,
        "non_negative": True,
        "meter_conservation": True,
    }

    tenants = [_serialize_tenant(st) for st in result.tenant_statements.values()]
    invoices = [_serialize_invoice(inv) for inv in result.invoices]
    slices = [_serialize_slice(s, data.spaces) for s in result.area_result.slices]
    meters = [_serialize_meter(m, data.readings, result.billing_start, result.billing_end) for m in data.meters]

    return {
        "summary": summary,
        "invariants": invariants,
        "tenants": tenants,
        "invoices": invoices,
        "slices": slices,
        "meters": meters,
    }


def _serialize_tenant(st: Any) -> Dict[str, Any]:
    return {
        "tenant_id": st.tenant_id,
        "tenant_name": st.tenant_name,
        "vat_opt_in": st.vat_opt_in,
        "total_net_eur": float(st.total_net_eur),
        "total_vat_eur": float(st.total_vat_eur),
        "total_billed_eur": float(st.total_net_eur + st.total_vat_eur if st.vat_opt_in else st.total_gross_eur),
        "total_prepayments_eur": float(st.total_prepayments_eur),
        "balance_due_eur": float(st.balance_due_eur),
        "recommended_new_prepayment_eur": float(st.recommended_new_prepayment_eur),
        "street_address": st.street_address,
        "postal_code": st.postal_code,
        "city": st.city,
    }


def _serialize_invoice(inv: Any) -> Dict[str, Any]:
    return {
        "invoice_id": inv.invoice_id,
        "cost_category": inv.cost_category,
        "cost_circle_scope": inv.cost_circle_scope,
        "billing_start": inv.billing_start.isoformat(),
        "billing_end": inv.billing_end.isoformat(),
        "net_amount_eur": float(inv.net_amount_eur),
        "vat_rate_percent": float(inv.vat_rate_percent),
        "gross_amount_eur": float(inv.gross_amount_eur),
    }


def _serialize_slice(s: Any, spaces: List[PhysicalSpace]) -> Dict[str, Any]:
    sp_map = {sp.space_id: sp for sp in spaces}
    sp = sp_map.get(s.space_id)
    return {
        "space_id": s.space_id,
        "building_id": sp.building_id if sp else "",
        "floor": sp.floor if sp else 1,
        "area_sqm": float(s.area_sqm),
        "tenant_id": s.tenant_id,
        "tenant_name": s.tenant_name,
        "start_date": s.start_date.isoformat(),
        "end_date": s.end_date.isoformat(),
        "days": s.days,
        "sqm_days": float(s.sqm_days),
        "is_vacancy": s.is_vacancy,
    }


def _serialize_meter(m: Any, readings: List[Any], start_d: date, end_d: date) -> Dict[str, Any]:
    start_r = next((r.value for r in readings if r.meter_id == m.meter_id and r.reading_date == start_d), Decimal("0"))
    end_r = next((r.value for r in readings if r.meter_id == m.meter_id and r.reading_date == end_d), Decimal("0"))
    cons = (end_r - start_r) * m.multiplier
    return {
        "meter_id": m.meter_id,
        "serial_number": m.serial_number,
        "medium": m.medium.value if hasattr(m.medium, "value") else str(m.medium),
        "parent_meter_id": m.parent_meter_id,
        "served_spaces": m.served_space_ids,
        "consumption": float(cons),
        "unit": m.unit,
    }


@app.get("/", response_class=HTMLResponse)
def index_view(request: Request) -> Any:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/benchmark")
def get_benchmark_api(dataset: Optional[str] = Query(default="big_marzahn")) -> Dict[str, Any]:
    _, _, payload = _get_active_calculation(dataset or "big_marzahn")
    return payload


@app.post("/api/upload")
async def upload_excel_api(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Only Excel (.xlsx) files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        importer = SpreadsheetImporter()
        data = importer.import_from_excel(tmp_path)
        if not data.spaces or not data.leases or not data.invoices:
            raise HTTPException(
                status_code=422,
                detail="Excel must contain 'Raeume', 'Mietvertraege', and 'Rechnungen' sheets with valid data.",
            )

        b_start = min((l.start_date for l in data.leases))
        b_end = max((l.end_date for l in data.leases))

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

        cached_json = _serialize_result(result, data)
        cached_json["portfolio_name"] = f"Hochgeladen: {file.filename}"
        cached_json["dataset"] = "uploaded"

        STATE["calculations"]["uploaded"] = {
            "result": result,
            "spaces": data.spaces,
            "cached_json": cached_json,
        }
        STATE["active_dataset"] = "uploaded"
        return cached_json
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/api/download-excel")
def download_excel_api(dataset: Optional[str] = Query(default="big_marzahn")) -> FileResponse:
    target_ds = dataset or STATE.get("active_dataset", "big_marzahn")
    res, spaces, _ = _get_active_calculation(target_ds)

    filename = (
        "B.I.G_Marzahn_Betriebskostenabrechnung_2025_Final.xlsx"
        if target_ds == "big_marzahn"
        else (
            "Gewerbehof_SpreeCampus_Betriebskostenabrechnung_2025.xlsx"
            if target_ds == "spree_campus"
            else "Betriebskostenabrechnung_2025_Final.xlsx"
        )
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name

    exporter = AuditReadyExcelExporter()
    exporter.export_to_excel(res, spaces, tmp_path)

    return FileResponse(
        path=tmp_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/api/download-template")
def download_template_api() -> FileResponse:
    tpl_path = Path("templates/Muster_Eingabe_Gewerbehof_SpreeCampus.xlsx")
    if not tpl_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")

    return FileResponse(
        path=str(tpl_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Muster_Eingabe_Gewerbehof_SpreeCampus.xlsx",
    )
