from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_ml_ready_tables_and_columns(db_session: Session) -> None:
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    assert "ml_training_examples" in tables
    assert "ml_predictions" in tables
    assert "mcp_payment_predictions" in tables

    training_columns = {column["name"] for column in inspector.get_columns("ml_training_examples")}
    for column in {
        "created_at",
        "input_json",
        "label",
        "claim_id",
        "mcp_code",
        "insurance_company_id",
    }:
        assert column in training_columns

    prediction_columns = {column["name"] for column in inspector.get_columns("ml_predictions")}
    for column in {
        "created_at",
        "model_version",
        "claim_id",
        "mcp_code",
        "insurance_company_id",
        "prediction",
    }:
        assert column in prediction_columns
