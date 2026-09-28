"""Domain enumerations for commercial utility calculator."""

from enum import Enum


class Medium(str, Enum):
    ELECTRICITY = "electricity"
    WATER = "water"
    HEATING = "heating"
    COOLING = "cooling"


class UsageType(str, Enum):
    OFFICE = "office"
    RETAIL = "retail"
    LIGHT_INDUSTRIAL = "light_industrial"
    STORAGE = "storage"
    MEDICAL = "medical"
    CANTEEN = "canteen"
    COMMON_AREA = "common_area"


class TaxMode(str, Enum):
    OPTED_IN_19 = "opted_in_19"
    EXEMPT_0 = "exempt_0"


class AnomalyAction(str, Enum):
    PROPORTIONAL_SCALING = "proportional_scaling"
    OVERHEAD_REALLOCATION = "overhead_reallocation"
