"""Versioned Cairn process-description core.

Copy this package to validate and parse a process without installing Deborah.
The version of this contract is ``CORE_VERSION``. It is not the Deborah
package version.
"""

from cairn_core.conformance import validate_plan
from cairn_core.metamodel import (
    CORE_VERSION,
    SPEC_VERSION,
    AnnotationRule,
    ValidationMetamodel,
    DEFAULT_METAMODEL,
)
from cairn_core.parser import parse_document
from cairn_core.validate import validate_document

CONFORMANCE_VERSION = DEFAULT_METAMODEL.conformance_version

__all__ = [
    "CORE_VERSION",
    "CONFORMANCE_VERSION",
    "SPEC_VERSION",
    "AnnotationRule",
    "DEFAULT_METAMODEL",
    "ValidationMetamodel",
    "parse_document",
    "validate_document",
    "validate_plan",
]
