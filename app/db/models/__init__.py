"""SQLAlchemy models for the application."""

from app.db.models.address import Address
from app.db.models.audit_log import AuditLog
from app.db.models.base import Base
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.claim import Claim
from app.db.models.claim_diagnosis_code import ClaimDiagnosisCode
from app.db.models.claim_line_coverage import ClaimLineCoverage
from app.db.models.claim_mcp_code import ClaimMcpCode
from app.db.models.claim_pdf import ClaimPDF
from app.db.models.claim_procedure_diagnosis import ClaimProcedureDiagnosis
from app.db.models.claim_procedure_fact import ClaimProcedureFact
from app.db.models.claim_status_check import ClaimStatusCheck
from app.db.models.clinic import Clinic
from app.db.models.diagnosis_code import DiagnosisCode
from app.db.models.enums import ClaimStatus
from app.db.models.insurance_card import InsuranceCard
from app.db.models.insurance_company import InsuranceCompany
from app.db.models.mcp_code import McpCode
from app.db.models.mcp_payment_prediction import McpPaymentPrediction
from app.db.models.ml_prediction import MlPrediction
from app.db.models.ml_training_example import MlTrainingExample
from app.db.models.patient import Patient
from app.db.models.patient_insurance_policy import PatientInsurancePolicy
from app.db.models.policy_link import PolicyLink
from app.db.models.policy_override import ClinicPolicyOverride, DoctorPolicyOverride
from app.db.models.policy_rule import PolicyRule
from app.db.models.role import Role
from app.db.models.user import User
from app.db.models.user_role import UserRole
from app.db.models.virtual_claim import VirtualClaimDraft, VirtualClaimField, VirtualClaimQuestion

__all__ = [
    "Base",
    "AuditLog",
    "ChatMessage",
    "ChatSession",
    "Claim",
    "ClaimDiagnosisCode",
    "ClaimLineCoverage",
    "ClaimMcpCode",
    "ClaimPDF",
    "ClaimProcedureDiagnosis",
    "ClaimProcedureFact",
    "ClaimStatusCheck",
    "Address",
    "Clinic",
    "ClaimStatus",
    "DiagnosisCode",
    "InsuranceCompany",
    "InsuranceCard",
    "McpCode",
    "McpPaymentPrediction",
    "MlPrediction",
    "MlTrainingExample",
    "Patient",
    "PatientInsurancePolicy",
    "ClinicPolicyOverride",
    "DoctorPolicyOverride",
    "PolicyLink",
    "PolicyRule",
    "Role",
    "User",
    "UserRole",
    "VirtualClaimDraft",
    "VirtualClaimField",
    "VirtualClaimQuestion",
]
