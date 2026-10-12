# ------------------------------------------------------------------------------
# Überprüft durch Claude  Hailku
# ==============================================================================

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    TSS = "tss"
    LEHRKRAFT = "lehrkraft"


# Vordefinierte Rollen-Gruppen für die Dekoratoren
_ALLOWED_ROLES_ADMIN = frozenset({UserRole.ADMIN})
_ALLOWED_ROLES_TSS = frozenset({UserRole.ADMIN, UserRole.TSS, UserRole.LEHRKRAFT})
