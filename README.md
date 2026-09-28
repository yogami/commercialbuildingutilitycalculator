# Commercial Building Utility & Cost Allocation Engine
### Gewerbliche Betriebskostenabrechnung nach § 259 BGB & BGH-Rechtsprechung

An audit-proof, deterministic calculation engine for German commercial real estate (Gewerbeimmobilien). Designed for commercial property and facility managers operating without an enterprise ERP who need to replace fragile, error-prone spreadsheets with verifiable accounting logic.

---

## Core Directives & Architecture

- **Zero LLMs in calculation path**: 100% deterministic pure Python, exact cent accounting using integer penny balancing (Hamilton / Hare-Niemeyer method).
- **Hexagonal Architecture (DDD)**:
  - `domain/`: Entities (`PhysicalSpace`, `Meter`, `TenantLease`, `CostInvoice`), enums, invariants.
  - `application/`: Domain services (Module A, B, C, D, E, Monthly readings, Engine orchestrator).
  - `infrastructure/`: Importers for German spreadsheets / CSVs, formula-backed Excel exporter (`openpyxl`).
- **Prüffähigkeit (§ 259 BGB)**: Exported Excel workbooks retain live formulas (`=B4*C4`, `=SUM(...)`), allowing tenant lawyers and auditors to verify every calculation step.

---

## Domain Calculation Modules

1. **Module A: Time-Weighted Area Allocation (m²-Tage)**
   - Tracks moves, lease expansions, and downsizings down to the exact calendar day.
   - Calculates area-days: `sum(occupied_sqm * active_days)`.
   - Vacancy absorption: Unleased periods are isolated and allocated to the landlord account (`LANDLORD_VACANCY`), as mandated by German tenancy law.

2. **Module B: Meter Hierarchy & Anomaly Balances (Zählerbaum & Differenzmessung)**
   - Models parent-child cascades as a Directed Acyclic Graph (DAG) with NetworkX.
   - Determines residual common-area base loads (hallway lighting, line losses, parasitic loads).
   - Enforces physical conservation checks.

3. **Module C: Technical Correction Factors (Angleichungsfaktor)**
   - Proportional scaling for reading date drift, transformer losses, and cable resistance.
   - Strict thresholds: 8% for electricity, 10% for water and heating.
   - If drift exceeds thresholds, the engine halts scaling and routes the entire excess to general building overhead (Allgemeinkosten). Raw and adjusted values are preserved side-by-side.

4. **Module D: Hybrid Metering & Direct Deductions (Vorwegabzug)**
   - Deducts clean submetered consumption first at unit cost.
   - Apportions the remaining unmetered pool strictly by participating square meters without double-billing.

5. **Module E: Multi-Building Cost Circles (Mehrhausanlagen nach Kostenkreisen)**
   - Respects BGH case law on *Wirtschaftseinheiten*. Avoids global campus cost pooling.
   - Technical installations (e.g. Building 1 elevator, campus sprinkler, shared chiller) compute independent area denominators matching their specific scope.

6. **Tax Treatment (§ 9 UStG)**
   - Handles mixed VAT commercial properties:
     - Opted tenants receive net cost shares plus explicit 19% VAT line items.
     - Exempt tenants (e.g. medical practices under § 4 Nr. 14 UStG) receive gross allocations.

7. **Monthly Meter Readings & Seasonal Weighting**
   - Handles monthly meter intervals for mid-year lease changes.
   - Applies DIN 4713 / VDI 2067 Heating Degree Day Promille tables for unmetered heating cost splits.

---

## The Four Invariant Test Gates

Before generating any statement, the engine verifies four non-negotiable assertions:
1. **The Penny Balance Check**: Sum of tenant charges + landlord vacancy charges == Total invoice amounts (0.00 EUR discrepancy).
2. **The Area Continuity Invariant**: For every calendar day in the billing year, Sum of tenant sqm + vacant sqm == Total physical building area.
3. **The Non-Negative Check**: Zero negative consumption, zero negative days, zero negative cost lines.
4. **Conservation Invariant**: Parent meter >= sum of submeters (unless marked as bidirectional solar feed).

---

## CLI Quickstart

### Run benchmark calculation:
```bash
uv run python -m commercial_utility_calculator.cli benchmark --output Gewerbehof_SpreeCampus_Abrechnung_2025.xlsx
```

### Run custom calculation from Excel:
```bash
uv run python -m commercial_utility_calculator.cli calculate \
  --input-excel templates/Muster_Eingabe_Gewerbehof_SpreeCampus.xlsx \
  --output Meine_Abrechnung_2025.xlsx \
  --start-date 2025-01-01 \
  --end-date 2025-12-31
```

### Generate blank CSV templates:
```bash
uv run python -m commercial_utility_calculator.cli generate-templates --output-dir templates
```

### Run Automated Tests & Coverage:
```bash
uv run pytest --cov=commercial_utility_calculator --cov-report=term-missing
```
