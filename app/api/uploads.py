from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.models.cpa import CPA
import tempfile
import os

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/upload-cpa-list")
async def upload_monthly_cpa_list(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload monthly OPLC CPA list (Excel file)"""

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="File must be Excel format (.xlsx or .xls)"
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        # Import CPAs
        import_service = CPAImportService(db)
        results = import_service.import_from_excel(tmp_file_path)

        return {
            "message": "CPA list uploaded successfully",
            "results": results,
            "filename": file.filename,
        }

    finally:
        # Clean up temp file
        os.unlink(tmp_file_path)


@router.post("/upload-cpe-certificate/{license_number}")
async def upload_cpe_certificate(
    license_number: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload CPE certificate for a CPA"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Upload to DO Spaces
    storage_service = DocumentStorageService()
    result = await storage_service.upload_cpe_certificate(file, license_number)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "message": "Certificate uploaded successfully",
        "file_info": result,
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
    }


@router.get("/cpa-documents/{license_number}")
async def list_cpa_documents(license_number: str, db: Session = Depends(get_db)):
    """List all uploaded documents for a CPA"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Get documents from Spaces
    storage_service = DocumentStorageService()
    documents = storage_service.list_cpa_documents(license_number)

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "documents": documents,
    }
