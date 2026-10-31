"""Start-up migration: databases created before evidence_json existed get the column added."""

from sqlalchemy import create_engine, inspect, text

from app.database import _add_missing_columns


def test_old_inspections_table_gains_evidence_column_and_keeps_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE inspections (id VARCHAR(36) PRIMARY KEY, image_filename VARCHAR(255))"))
        conn.execute(text("INSERT INTO inspections VALUES ('abc', 'old.jpg')"))
        _add_missing_columns(conn)
        _add_missing_columns(conn)  # running twice must be harmless

    columns = {c["name"] for c in inspect(engine).get_columns("inspections")}
    assert "evidence_json" in columns
    assert "product_name" in columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT image_filename, evidence_json FROM inspections")).one() == ("old.jpg", None)
