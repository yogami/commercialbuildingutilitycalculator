"""Tests for the B.I.G. Marzahn commercial campus data importer."""

from pathlib import Path
import pytest

from commercial_utility_calculator.infrastructure.importers.big_marzahn_importer import (
    BigMarzahnImporter,
)


@pytest.fixture
def data_dir() -> Path:
    return Path("data/input_bka_2025")


def test_import_big_marzahn_property_data(data_dir: Path) -> None:
    if not (data_dir / "Vermietete_Flächen_2025.xlsx").exists():
        pytest.skip("Local BKA 2025 data not downloaded")

    importer = BigMarzahnImporter()
    data = importer.load_all_data(data_dir)

    # 1. Spaces and leases
    assert len(data.spaces) > 0
    assert len(data.leases) > 0
    assert any("Scansonic" in l.tenant_name for l in data.leases)
    assert any("Gefertec" in l.tenant_name for l in data.leases)

    # 2. Invoices
    assert len(data.invoices) > 0
    grundsteuer_inv = next((inv for inv in data.invoices if "Grundsteuer" in inv.cost_category), None)
    assert grundsteuer_inv is not None
    assert grundsteuer_inv.net_amount_eur > 40000

    # 3. Addresses
    matching_lease = next((l for l in data.leases if "Scansonic" in l.tenant_name), None)
    assert matching_lease is not None
    assert matching_lease.postal_code is not None or matching_lease.city is not None
