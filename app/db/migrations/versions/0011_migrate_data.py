"""Migrate data from old schema into new schema tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_migrate_data"
down_revision = "0010_expand_new_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_users (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM users_old
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH ordered AS (
                SELECT
                    u.id,
                    u.email,
                    u.full_name,
                    u.hashed_password,
                    u.is_active,
                    u.created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY u.email
                        ORDER BY u.created_at NULLS LAST, u.id
                    ) AS rn
                FROM users_old u
            ),
            normalized AS (
                SELECT
                    o.*,
                    CASE
                        WHEN o.rn = 1 THEN o.email
                        WHEN POSITION('@' IN o.email) > 1 THEN
                            SPLIT_PART(o.email, '@', 1) || '+dup' || o.rn || '@' || SPLIT_PART(o.email, '@', 2)
                        ELSE o.email || '+dup' || o.rn
                    END AS email_unique
                FROM ordered o
            )
            INSERT INTO users (id, email, password_hash, full_name, is_active, created_at)
            SELECT
                map.new_id,
                n.email_unique,
                n.hashed_password,
                n.full_name,
                n.is_active,
                n.created_at::timestamp
            FROM normalized n
            JOIN id_map_users map ON map.old_uuid = n.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO roles (id, code, description)
            VALUES
                (1, 'admin', 'Administrator'),
                (2, 'doctor', 'Doctor')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT map.new_id, 2
            FROM users_old u
            JOIN id_map_users map ON map.old_uuid = u.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT map.new_id, 1
            FROM users_old u
            JOIN id_map_users map ON map.old_uuid = u.id
            WHERE u.is_admin IS TRUE
            """
        )
    )

    conn.execute(
        sa.text(
            """
            WITH distinct_companies AS (
                SELECT DISTINCT ON (a.name) a.id, a.name, a.created_at
                FROM agencies a
                ORDER BY a.name, a.created_at NULLS LAST, a.id
            ),
            numbered AS (
                SELECT
                    id AS old_uuid,
                    name,
                    created_at,
                    ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id) AS new_id
                FROM distinct_companies
            )
            INSERT INTO insurance_companies (id, name, created_at)
            SELECT new_id, name, created_at::timestamp
            FROM numbered
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH distinct_companies AS (
                SELECT DISTINCT ON (a.name) a.id, a.name, a.created_at
                FROM agencies a
                ORDER BY a.name, a.created_at NULLS LAST, a.id
            ),
            numbered AS (
                SELECT
                    id AS old_uuid,
                    name,
                    ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id) AS new_id
                FROM distinct_companies
            )
            INSERT INTO id_map_insurance_companies (old_uuid, new_id)
            SELECT a.id, n.new_id
            FROM agencies a
            JOIN numbered n ON a.name = n.name
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO mcp_codes (code, description)
            SELECT DISTINCT ON (pc.code)
                pc.code,
                COALESCE(pc.title, pc.code)
            FROM procedure_codes pc
            ORDER BY pc.code, pc.updated_at DESC NULLS LAST, pc.created_at DESC NULLS LAST, pc.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO diagnosis_codes (code, description)
            SELECT DISTINCT ON (d.code)
                d.code,
                COALESCE(d.title, d.code)
            FROM diagnoses d
            ORDER BY d.code, d.updated_at DESC NULLS LAST, d.created_at DESC NULLS LAST, d.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            WITH raw AS (
                SELECT
                    apl.id,
                    map.new_id AS insurance_company_id,
                    pc.code AS mcp_code,
                    apl.policy_url,
                    apl.created_at,
                    apl.updated_at
                FROM agency_procedure_policy_links apl
                JOIN id_map_insurance_companies map ON map.old_uuid = apl.agency_id
                JOIN procedure_codes pc ON pc.id = apl.procedure_code_id
            ),
            dedup AS (
                SELECT DISTINCT ON (insurance_company_id, mcp_code, policy_url)
                    *
                FROM raw
                ORDER BY
                    insurance_company_id,
                    mcp_code,
                    policy_url,
                    updated_at DESC NULLS LAST,
                    created_at DESC NULLS LAST,
                    id
            ),
            numbered AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY insurance_company_id, mcp_code, policy_url
                    ) AS new_id,
                    insurance_company_id,
                    mcp_code,
                    policy_url,
                    created_at
                FROM dedup
            )
            INSERT INTO policy_links (id, insurance_company_id, mcp_code, policy_url, created_at)
            SELECT new_id, insurance_company_id, mcp_code, policy_url, created_at::timestamp
            FROM numbered
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_patients (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM patients_old
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH tenant_default_user AS (
                SELECT
                    tenant_id,
                    id AS user_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY tenant_id ORDER BY created_at NULLS LAST, id
                    ) AS rn
                FROM users_old
            ),
            default_user AS (
                SELECT tenant_id, user_id
                FROM tenant_default_user
                WHERE rn = 1
            ),
            fallback_user AS (
                SELECT id AS user_id
                FROM users_old
                ORDER BY created_at NULLS LAST, id
                LIMIT 1
            )
            INSERT INTO patients (id, doctor_id, first_name, last_name, date_of_birth, created_at)
            SELECT
                map.new_id,
                user_map.new_id,
                p.first_name,
                p.last_name,
                p.dob,
                p.created_at::timestamp
            FROM patients_old p
            JOIN id_map_patients map ON map.old_uuid = p.id
            LEFT JOIN default_user du ON du.tenant_id = p.tenant_id
            CROSS JOIN fallback_user fu
            JOIN id_map_users user_map
                ON user_map.old_uuid = COALESCE(p.user_id, du.user_id, fu.user_id)
            """
        )
    )

    needs_unknown = conn.execute(
        sa.text("SELECT 1 FROM claims_old WHERE agency_id IS NULL LIMIT 1")
    ).fetchone()
    unknown_id = None
    if needs_unknown:
        existing = conn.execute(
            sa.text("SELECT id FROM insurance_companies WHERE name = 'Unknown' LIMIT 1")
        ).fetchone()
        if existing:
            unknown_id = int(existing[0])
        else:
            max_id = conn.execute(
                sa.text("SELECT COALESCE(MAX(id), 0) FROM insurance_companies")
            ).scalar_one()
            unknown_id = int(max_id or 0) + 1
            conn.execute(
                sa.text(
                    """
                    INSERT INTO insurance_companies (id, name, created_at)
                    VALUES (:id, 'Unknown', NULL)
                    """
                ),
                {"id": unknown_id},
            )

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_claims (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM claims_old
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH procedure_totals AS (
                SELECT
                    claim_id,
                    SUM(coinsurance_amount_cents) / 100.0 AS coinsurance_amount_total,
                    SUM(copay_amount_cents) / 100.0 AS copay_amount_total,
                    SUM(deductible_amount_cents) / 100.0 AS deductible_amount_total
                FROM claim_procedures
                GROUP BY claim_id
            )
            INSERT INTO claims (
                id,
                doctor_id,
                patient_id,
                insurance_company_id,
                service_date,
                created_at,
                claim_number,
                claim_status,
                claim_date,
                billed_amount_total,
                allowed_amount_total,
                coinsurance_amount_total,
                copay_amount_total,
                deductible_amount_total
            )
            SELECT
                map.new_id,
                p_new.doctor_id,
                p_new.id,
                COALESCE(company_map.new_id, :unknown_id),
                COALESCE(c.service_from, c.service_to),
                c.created_at::timestamp,
                c.claim_number,
                c.status::text,
                COALESCE(c.received_at::date, c.created_at::date),
                c.billed_total_cents / 100.0,
                c.allowed_total_cents / 100.0,
                totals.coinsurance_amount_total,
                totals.copay_amount_total,
                totals.deductible_amount_total
            FROM claims_old c
            JOIN id_map_claims map ON map.old_uuid = c.id
            JOIN id_map_patients patient_map ON patient_map.old_uuid = c.patient_id
            JOIN patients p_new ON p_new.id = patient_map.new_id
            LEFT JOIN id_map_insurance_companies company_map ON company_map.old_uuid = c.agency_id
            LEFT JOIN procedure_totals totals ON totals.claim_id = c.id
            """
        ),
        {"unknown_id": unknown_id},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO claim_mcp_codes (claim_id, mcp_code)
            SELECT DISTINCT map.new_id, pc.code
            FROM claim_procedures cp
            JOIN id_map_claims map ON map.old_uuid = cp.claim_id
            JOIN procedure_codes pc ON pc.id = cp.procedure_code_id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO claim_diagnosis_codes (claim_id, diagnosis_code)
            SELECT DISTINCT map.new_id, d.code
            FROM claim_diagnoses cd
            JOIN id_map_claims map ON map.old_uuid = cd.claim_id
            JOIN diagnoses d ON d.id = cd.diagnosis_id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_claim_procedures (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM claim_procedures
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH payments AS (
                SELECT
                    claim_procedure_id,
                    SUM(paid_amount_cents) / 100.0 AS paid_amount,
                    MAX(paid_at)::date AS paid_at
                FROM claim_procedure_payments
                GROUP BY claim_procedure_id
            )
            INSERT INTO claim_procedure_facts (
                id,
                claim_id,
                patient_id,
                insurance_company_id,
                mcp_code,
                service_date,
                units,
                modifier,
                billed_amount,
                allowed_amount,
                coinsurance_amount,
                copay_amount,
                deductible_amount,
                paid_amount,
                paid_at,
                created_at
            )
            SELECT
                proc_map.new_id,
                claim_map.new_id,
                claim_new.patient_id,
                claim_new.insurance_company_id,
                pc.code,
                claim_new.service_date,
                cp.units::numeric,
                cp.modifier,
                cp.billed_amount_cents / 100.0,
                cp.allowed_amount_cents / 100.0,
                cp.coinsurance_amount_cents / 100.0,
                cp.copay_amount_cents / 100.0,
                cp.deductible_amount_cents / 100.0,
                COALESCE(payments.paid_amount, cp.paid_amount_cents / 100.0),
                payments.paid_at,
                cp.created_at::timestamp
            FROM claim_procedures cp
            JOIN id_map_claim_procedures proc_map ON proc_map.old_uuid = cp.id
            JOIN id_map_claims claim_map ON claim_map.old_uuid = cp.claim_id
            JOIN claims claim_new ON claim_new.id = claim_map.new_id
            JOIN procedure_codes pc ON pc.id = cp.procedure_code_id
            LEFT JOIN payments ON payments.claim_procedure_id = cp.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO claim_procedure_diagnosis (claim_procedure_fact_id, diagnosis_code)
            SELECT fact.id, diag.diagnosis_code
            FROM claim_procedure_facts fact
            JOIN claim_diagnosis_codes diag ON diag.claim_id = fact.claim_id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_chat_sessions (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM chat_sessions_old
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO chat_sessions (id, doctor_id, created_at, title)
            SELECT
                map.new_id,
                user_map.new_id,
                cs.created_at::timestamp,
                CASE
                    WHEN cs.claim_id IS NOT NULL
                        THEN COALESCE('Claim ' || c.claim_number, 'Claim session')
                    ELSE 'Chat session'
                END
            FROM chat_sessions_old cs
            JOIN id_map_chat_sessions map ON map.old_uuid = cs.id
            JOIN id_map_users user_map ON user_map.old_uuid = cs.user_id
            LEFT JOIN claims_old c ON c.id = cs.claim_id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO id_map_chat_messages (old_uuid, new_id)
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id)
            FROM chat_messages_old
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO chat_messages (id, session_id, role, content, created_at)
            SELECT
                msg_map.new_id,
                session_map.new_id,
                cm.role,
                COALESCE(
                    cm.content,
                    CASE
                        WHEN cm.tool_name IS NOT NULL
                             OR cm.tool_args IS NOT NULL
                             OR cm.tool_result IS NOT NULL
                            THEN '[tool] '
                                || COALESCE(cm.tool_name, '')
                                || ' args='
                                || COALESCE(cm.tool_args::text, '{}')
                                || ' result='
                                || COALESCE(cm.tool_result::text, '{}')
                        ELSE '(empty)'
                    END
                ),
                cm.created_at::timestamp
            FROM chat_messages_old cm
            JOIN id_map_chat_messages msg_map ON msg_map.old_uuid = cm.id
            JOIN id_map_chat_sessions session_map ON session_map.old_uuid = cm.session_id
            """
        )
    )

    def _count(query: str, params: dict | None = None) -> int:
        return int(conn.execute(sa.text(query), params or {}).scalar_one())

    users_old_count = _count("SELECT COUNT(*) FROM users_old")
    users_count = _count("SELECT COUNT(*) FROM users")
    if users_old_count != users_count:
        raise ValueError(f"users count mismatch: {users_old_count} -> {users_count}")

    patients_old_count = _count("SELECT COUNT(*) FROM patients_old")
    patients_count = _count("SELECT COUNT(*) FROM patients")
    if patients_old_count != patients_count:
        raise ValueError(f"patients count mismatch: {patients_old_count} -> {patients_count}")

    claims_old_count = _count("SELECT COUNT(*) FROM claims_old")
    claims_count = _count("SELECT COUNT(*) FROM claims")
    if claims_old_count != claims_count:
        raise ValueError(f"claims count mismatch: {claims_old_count} -> {claims_count}")

    sessions_old_count = _count("SELECT COUNT(*) FROM chat_sessions_old")
    sessions_count = _count("SELECT COUNT(*) FROM chat_sessions")
    if sessions_old_count != sessions_count:
        raise ValueError(
            f"chat_sessions count mismatch: {sessions_old_count} -> {sessions_count}"
        )

    messages_old_count = _count("SELECT COUNT(*) FROM chat_messages_old")
    messages_count = _count("SELECT COUNT(*) FROM chat_messages")
    if messages_old_count != messages_count:
        raise ValueError(
            f"chat_messages count mismatch: {messages_old_count} -> {messages_count}"
        )

    agencies_old_count = _count("SELECT COUNT(*) FROM agencies")
    companies_count = _count("SELECT COUNT(*) FROM insurance_companies")
    if agencies_old_count > 0 and companies_count == 0:
        raise ValueError("insurance_companies migration produced 0 rows")
    if companies_count > agencies_old_count:
        raise ValueError(
            "insurance_companies count exceeds agencies count, expected dedupe only"
        )

    null_claim_company = _count(
        "SELECT COUNT(*) FROM claims WHERE insurance_company_id IS NULL"
    )
    if null_claim_company > 0:
        raise ValueError("claims have NULL insurance_company_id after migration")


def downgrade() -> None:
    pass
