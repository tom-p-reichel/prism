"""
Supplies utilities for querying OCaml package information.
"""

from .api import OpamAPI  # noqa: F401
from .formula import (  # noqa: F401
    AssignedVariables,
    PackageFormula,
    Variable,
    VersionFormula,
)
from .switch import OpamSwitch  # noqa: F401
from .util import major_minor_version_bound  # noqa: F401
from .version import (  # noqa: F401
    OCamlVersion,
    OpamVersion,
    ParseError,
    Version,
)
from .versiondist import (
    VersionDistribution
)
