"""Persist why a capability came back unverified, not only what it costs.

The probe already computed the reasons — «inventó un teléfono que el CV no
trae», «no devolvió una respuesta con la estructura requerida» — and the
service dropped them on the floor, so the screen could only show the generic
function lost. FR-007.3 and SC-016 ask for informed degradation, and naming the
consequence without the cause is half of it.

It is a column and not a value recomputed on read because the reason belongs to
**that** preflight, of **that** model, with **that** credential. Recomputing it
later would mean probing the provider again on every page load, and inferring it
from the result would mean inventing it.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_configurations",
        sa.Column(
            "degradation_reasons",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    # The same shape the rest of the table already has: a column that only makes
    # sense for one result may not carry data under any other. `degradation_
    # acknowledged_at` is constrained this way for the same reason — the database
    # refuses to represent a degradation nobody degraded.
    op.create_check_constraint(
        "reasons_only_when_unverified",
        "provider_configurations",
        "degradation_reasons = '{}' OR preflight_result = 'capability_unverified'",
    )


def downgrade() -> None:
    op.drop_constraint("reasons_only_when_unverified", "provider_configurations", type_="check")
    op.drop_column("provider_configurations", "degradation_reasons")
