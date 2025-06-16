from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
import tempfile
import os

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.post("/upload-cpa-list")
async def upload_monthly_cpa_list(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload monthly OPLC CPA list (Excel file)"""
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="File must be Excel format (.xlsx or .xls)"
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
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
            "filename": file.filename
        }
        
    finally:
        # Clean up temp file
        os.unlink(tmp_file_path)
