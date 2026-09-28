"""Synthetic benchmark dataset generator: Gewerbehof Spree-Campus Berlin."""

from datetime import date
from decimal import Decimal
from typing import List

from commercial_utility_calculator.domain.entities import (
    CostInvoice,
    Meter,
    MeterReading,
    PhysicalSpace,
    TenantLease,
)
from commercial_utility_calculator.domain.enums import Medium, UsageType
from commercial_utility_calculator.infrastructure.importers.spreadsheet_importer import ParsedPropertyData


def create_spree_campus_benchmark() -> ParsedPropertyData:
    """Creates a realistic German commercial property portfolio with 3 buildings and 7 tenants."""
    spaces: List[PhysicalSpace] = [
        # Building A: Office & Medical
        PhysicalSpace(
            space_id="SP-A-101",
            building_id="BLDG-A",
            floor=1,
            room_number="101",
            area_sqm=Decimal("300.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-A", "ELEVATOR-BLDG-A"],
        ),
        PhysicalSpace(
            space_id="SP-A-201",
            building_id="BLDG-A",
            floor=2,
            room_number="201",
            area_sqm=Decimal("250.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-A", "ELEVATOR-BLDG-A"],
        ),
        PhysicalSpace(
            space_id="SP-A-202",
            building_id="BLDG-A",
            floor=2,
            room_number="202",
            area_sqm=Decimal("150.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-A", "ELEVATOR-BLDG-A"],
        ),
        PhysicalSpace(
            space_id="SP-A-301",
            building_id="BLDG-A",
            floor=3,
            room_number="301",
            area_sqm=Decimal("300.00"),
            usage_type=UsageType.MEDICAL,
            cost_circle_scope=["CAMPUS", "BLDG-A", "ELEVATOR-BLDG-A"],
        ),
        # Building B: R&D and Loft Offices (No Elevator)
        PhysicalSpace(
            space_id="SP-B-101",
            building_id="BLDG-B",
            floor=1,
            room_number="101",
            area_sqm=Decimal("400.00"),
            usage_type=UsageType.LIGHT_INDUSTRIAL,
            cost_circle_scope=["CAMPUS", "BLDG-B"],
        ),
        PhysicalSpace(
            space_id="SP-B-201",
            building_id="BLDG-B",
            floor=2,
            room_number="201",
            area_sqm=Decimal("350.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-B"],
        ),
        # Building C: Logistics & Canteen
        PhysicalSpace(
            space_id="SP-C-101",
            building_id="BLDG-C",
            floor=1,
            room_number="101",
            area_sqm=Decimal("500.00"),
            usage_type=UsageType.STORAGE,
            cost_circle_scope=["CAMPUS", "BLDG-C"],
        ),
        PhysicalSpace(
            space_id="SP-C-102",
            building_id="BLDG-C",
            floor=1,
            room_number="102",
            area_sqm=Decimal("150.00"),
            usage_type=UsageType.CANTEEN,
            cost_circle_scope=["CAMPUS", "BLDG-C"],
        ),
    ]

    leases: List[TenantLease] = [
        TenantLease(
            lease_id="L-A101",
            tenant_id="T-TECH",
            tenant_name="TechBerlin Solutions GmbH",
            space_id="SP-A-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("800.00"),
        ),
        # TechBerlin expands into SP-A-202 on July 1st (Jan 1 - June 30 vacant)
        TenantLease(
            lease_id="L-A202",
            tenant_id="T-TECH",
            tenant_name="TechBerlin Solutions GmbH",
            space_id="SP-A-202",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("400.00"),
        ),
        TenantLease(
            lease_id="L-A201",
            tenant_id="T-LAW",
            tenant_name="Kanzlei Spree & Partner",
            space_id="SP-A-201",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("650.00"),
        ),
        # Medical practice: VAT exempt (§ 4 Nr. 14 UStG)
        TenantLease(
            lease_id="L-A301",
            tenant_id="T-MED",
            tenant_name="Gemeinschaftspraxis Dr. Bergmann",
            space_id="SP-A-301",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=False,
            monthly_prepayment_eur=Decimal("900.00"),
        ),
        TenantLease(
            lease_id="L-B101",
            tenant_id="T-LAB",
            tenant_name="BioTech Labs Berlin GmbH",
            space_id="SP-B-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("1100.00"),
        ),
        # DesignStudio vacates on Sept 30 (Oct 1 - Dec 31 vacant)
        TenantLease(
            lease_id="L-B201",
            tenant_id="T-DESIGN",
            tenant_name="DesignStudio Kreuzberg GbR",
            space_id="SP-B-201",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 9, 30),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("700.00"),
        ),
        TenantLease(
            lease_id="L-C101",
            tenant_id="T-LOG",
            tenant_name="Spree LogistikHub GmbH",
            space_id="SP-C-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("950.00"),
        ),
        TenantLease(
            lease_id="L-C102",
            tenant_id="T-GASTRO",
            tenant_name="Campus GastroKonzepte GmbH",
            space_id="SP-C-102",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("500.00"),
        ),
    ]

    meters: List[Meter] = [
        Meter(meter_id="M-ROOT-E", serial_number="SN-E-001", medium=Medium.ELECTRICITY, parent_meter_id=None),
        Meter(meter_id="M-SUB-A", serial_number="SN-E-002", medium=Medium.ELECTRICITY, parent_meter_id="M-ROOT-E", served_space_ids=["SP-A-101", "SP-A-201", "SP-A-202", "SP-A-301"]),
        Meter(meter_id="M-SUB-LAB", serial_number="SN-E-003", medium=Medium.ELECTRICITY, parent_meter_id="M-ROOT-E", served_space_ids=["SP-B-101"]),
    ]

    readings: List[MeterReading] = [
        MeterReading(meter_id="M-ROOT-E", reading_date=date(2025, 1, 1), value=Decimal("100000.0")),
        MeterReading(meter_id="M-ROOT-E", reading_date=date(2025, 12, 31), value=Decimal("280000.0")),
        MeterReading(meter_id="M-SUB-A", reading_date=date(2025, 1, 1), value=Decimal("20000.0")),
        MeterReading(meter_id="M-SUB-A", reading_date=date(2025, 12, 31), value=Decimal("90000.0")),
        MeterReading(meter_id="M-SUB-LAB", reading_date=date(2025, 1, 1), value=Decimal("10000.0")),
        MeterReading(meter_id="M-SUB-LAB", reading_date=date(2025, 12, 31), value=Decimal("110000.0")),
    ]

    invoices: List[CostInvoice] = [
        CostInvoice(
            invoice_id="INV-01-GRUNDSTEUER",
            cost_category="Grundsteuer",
            net_amount_eur=Decimal("7200.00"),
            vat_rate_percent=Decimal("0.0"),
            gross_amount_eur=Decimal("7200.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="CAMPUS",
        ),
        CostInvoice(
            invoice_id="INV-02-HAUSMEISTER",
            cost_category="Hausmeister & Gruenpflege",
            net_amount_eur=Decimal("9600.00"),
            vat_rate_percent=Decimal("19.0"),
            gross_amount_eur=Decimal("11424.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="CAMPUS",
        ),
        CostInvoice(
            invoice_id="INV-03-AUFZUG-A",
            cost_category="Aufzugswartung & Notruf",
            asset_id="ASSET-ELEV-A",
            net_amount_eur=Decimal("2400.00"),
            vat_rate_percent=Decimal("19.0"),
            gross_amount_eur=Decimal("2856.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="ELEVATOR-BLDG-A",
        ),
        CostInvoice(
            invoice_id="INV-04-SPRINKLER",
            cost_category="Brandschutz & Sprinkleranlage",
            asset_id="ASSET-SPRINKLER",
            net_amount_eur=Decimal("4800.00"),
            vat_rate_percent=Decimal("19.0"),
            gross_amount_eur=Decimal("5712.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="CAMPUS",
        ),
        CostInvoice(
            invoice_id="INV-05-STROM-ALLGEMEIN",
            cost_category="Allgemeinstrom",
            net_amount_eur=Decimal("5400.00"),
            vat_rate_percent=Decimal("19.0"),
            gross_amount_eur=Decimal("6426.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="CAMPUS",
        ),
        CostInvoice(
            invoice_id="INV-06-MUELL",
            cost_category="Abfallbeseitigung",
            net_amount_eur=Decimal("3800.00"),
            vat_rate_percent=Decimal("0.0"),
            gross_amount_eur=Decimal("3800.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="CAMPUS",
        ),
    ]

    return ParsedPropertyData(
        spaces=spaces,
        meters=meters,
        readings=readings,
        leases=leases,
        invoices=invoices,
    )
