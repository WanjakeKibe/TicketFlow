"""Create the initial migration revision.

The domain tables will be introduced with the Phase 2 data model.
"""

from collections.abc import Sequence


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
