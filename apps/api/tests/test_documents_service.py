import datetime as dt
import io

import sqlalchemy as sa
from fastapi import UploadFile
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Base
from tickerlens_api.documents import service as documents_service


def _make_db() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_upload_document_creates_versioned_docs(monkeypatch) -> None:
    db = _make_db()

    uploaded = []

    def fake_put_object_fileobj(*, bucket: str, key: str, fileobj, content_type: str | None):
        uploaded.append((bucket, key, content_type, fileobj.read()))
        return None

    monkeypatch.setattr(documents_service, "put_object_fileobj", fake_put_object_fileobj)

    file1 = UploadFile(filename="a.pdf", file=io.BytesIO(b"hello"), headers=None)
    doc1, _, dedup1 = documents_service.upload_document(
        db,
        file=file1,
        ticker="INFY",
        company_name="Infosys",
        document_type="annual_report",
        fiscal_year="FY24",
        filing_date=dt.date(2024, 5, 12),
        source_url=None,
    )
    assert dedup1 is False
    assert doc1.version == 1

    file2 = UploadFile(filename="a.pdf", file=io.BytesIO(b"hello"), headers=None)
    doc2, _, dedup2 = documents_service.upload_document(
        db,
        file=file2,
        ticker="INFY",
        company_name="Infosys",
        document_type="annual_report",
        fiscal_year="FY24",
        filing_date=dt.date(2024, 5, 12),
        source_url=None,
    )
    assert dedup2 is True
    assert doc2.doc_id == doc1.doc_id

    file3 = UploadFile(filename="a.pdf", file=io.BytesIO(b"hello v2"), headers=None)
    doc3, _, dedup3 = documents_service.upload_document(
        db,
        file=file3,
        ticker="INFY",
        company_name="Infosys",
        document_type="annual_report",
        fiscal_year="FY24",
        filing_date=dt.date(2024, 5, 12),
        source_url=None,
    )
    assert dedup3 is False
    assert doc3.version == 2
    assert doc3.doc_id != doc1.doc_id

