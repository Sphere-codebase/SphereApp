"""Contract old schema and remove legacy tables/enums."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_contract_drop_old_schema"
down_revision = "0011_migrate_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("claim_events")
    op.drop_table("chat_messages_old")
    op.drop_table("chat_sessions_old")
    op.drop_table("payments")
    op.drop_table("claim_procedure_payments")
    op.drop_table("claim_diagnoses")
    op.drop_table("claim_procedures")
    op.drop_table("claim_visits")
    op.drop_table("visits")
    op.drop_table("patient_diagnoses")
    op.drop_table("claims_old")
    op.drop_table("patients_old")
    op.drop_table("procedure_price_by_agency")
    op.drop_table("agency_procedure_policy_links")
    op.drop_table("procedure_codes")
    op.drop_table("diagnoses")
    op.drop_table("agencies")
    op.drop_table("users_old")
    op.drop_table("tenants")

    op.drop_table("id_map_claim_procedures")
    op.drop_table("id_map_chat_messages")
    op.drop_table("id_map_chat_sessions")
    op.drop_table("id_map_claims")
    op.drop_table("id_map_patients")
    op.drop_table("id_map_insurance_companies")
    op.drop_table("id_map_users")

    op.execute(sa.text("DROP TYPE IF EXISTS policy_link_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS claim_status"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for contract migration.")
