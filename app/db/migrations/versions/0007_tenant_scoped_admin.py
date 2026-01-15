"""Scope admin catalogs to tenant."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_tenant_scoped_admin"
down_revision = "0006_ml_ready_schema_v1"
branch_labels = None
depends_on = None


def _get_default_tenant_id() -> uuid.UUID:
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT id FROM tenants ORDER BY created_at ASC LIMIT 1"))
    row = existing.first()
    if row is not None:
        return uuid.UUID(str(row[0]))
    new_id = uuid.uuid4()
    bind.execute(
        sa.text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
        {"id": new_id, "name": "Default Tenant"},
    )
    return new_id


def upgrade() -> None:
    default_tenant_id = _get_default_tenant_id()
    bind = op.get_bind()

    op.add_column(
        "agencies",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    bind.execute(
        sa.text("UPDATE agencies SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": default_tenant_id},
    )
    op.alter_column("agencies", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_agencies_tenant_id",
        "agencies",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_agencies_tenant_id", "agencies", ["tenant_id"])
    op.drop_constraint("uq_agencies_slug", "agencies", type_="unique")
    op.create_unique_constraint("uq_agencies_tenant_slug", "agencies", ["tenant_id", "slug"])

    op.add_column(
        "procedure_codes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    bind.execute(
        sa.text(
            "UPDATE procedure_codes SET tenant_id = :tenant_id WHERE tenant_id IS NULL"
        ),
        {"tenant_id": default_tenant_id},
    )
    op.alter_column("procedure_codes", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_procedure_codes_tenant_id",
        "procedure_codes",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_procedure_codes_tenant_id", "procedure_codes", ["tenant_id"])
    op.drop_constraint("uq_procedure_codes_code", "procedure_codes", type_="unique")
    op.create_unique_constraint(
        "uq_procedure_codes_tenant_code",
        "procedure_codes",
        ["tenant_id", "code"],
    )

    op.add_column(
        "diagnoses",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    bind.execute(
        sa.text("UPDATE diagnoses SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": default_tenant_id},
    )
    op.alter_column("diagnoses", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_diagnoses_tenant_id",
        "diagnoses",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_diagnoses_tenant_id", "diagnoses", ["tenant_id"])

    op.add_column(
        "agency_procedure_policy_links",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE agency_procedure_policy_links SET tenant_id = agencies.tenant_id "
        "FROM agencies WHERE agency_procedure_policy_links.agency_id = agencies.id"
    )
    op.alter_column("agency_procedure_policy_links", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_policy_links_tenant_id",
        "agency_procedure_policy_links",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_policy_links_tenant_id", "agency_procedure_policy_links", ["tenant_id"]
    )
    op.drop_index("uq_policy_links_active", table_name="agency_procedure_policy_links")
    op.create_index(
        "uq_policy_links_active_tenant",
        "agency_procedure_policy_links",
        ["tenant_id", "agency_id", "procedure_code_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_policy_links_active_tenant", table_name="agency_procedure_policy_links")
    op.create_index(
        "uq_policy_links_active",
        "agency_procedure_policy_links",
        ["agency_id", "procedure_code_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_index("ix_policy_links_tenant_id", table_name="agency_procedure_policy_links")
    op.drop_constraint(
        "fk_policy_links_tenant_id", "agency_procedure_policy_links", type_="foreignkey"
    )
    op.drop_column("agency_procedure_policy_links", "tenant_id")

    op.drop_index("ix_diagnoses_tenant_id", table_name="diagnoses")
    op.drop_constraint("fk_diagnoses_tenant_id", "diagnoses", type_="foreignkey")
    op.drop_column("diagnoses", "tenant_id")

    op.drop_constraint("uq_procedure_codes_tenant_code", "procedure_codes", type_="unique")
    op.create_unique_constraint("uq_procedure_codes_code", "procedure_codes", ["code"])
    op.drop_index("ix_procedure_codes_tenant_id", table_name="procedure_codes")
    op.drop_constraint("fk_procedure_codes_tenant_id", "procedure_codes", type_="foreignkey")
    op.drop_column("procedure_codes", "tenant_id")

    op.drop_constraint("uq_agencies_tenant_slug", "agencies", type_="unique")
    op.create_unique_constraint("uq_agencies_slug", "agencies", ["slug"])
    op.drop_index("ix_agencies_tenant_id", table_name="agencies")
    op.drop_constraint("fk_agencies_tenant_id", "agencies", type_="foreignkey")
    op.drop_column("agencies", "tenant_id")
