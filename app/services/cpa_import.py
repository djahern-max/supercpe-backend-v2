import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.cpa import CPA
from typing import List, Dict

class CPAImportService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def import_from_excel(self, file_path: str) -> Dict[str, int]:
        """
        Import CPAs from OPLC monthly Excel file
        Expected columns:
        - Profession
        - License Type  
        - License Number
        - Issue Date
        - Expiration Date
        - License Status
        - First Name
        - Last Name
        - Full Name/Business Name
        
        Returns: {"created": 5, "updated": 23, "errors": 0}
        """
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Filter for CPAs only (in case file has other professions)
            df = df[df['License Type'] == 'Certified Public Accountant'].copy()
            
            results = {"created": 0, "updated": 0, "errors": 0, "skipped": 0}
            
            for _, row in df.iterrows():
                try:
                    license_number = str(row['License Number']).strip()
                    full_name = str(row['Full Name/Business Name']).strip()
                    
                    # Parse dates - handle different formats
                    issue_date = pd.to_datetime(row['Issue Date']).date()
                    expiration_date = pd.to_datetime(row['Expiration Date']).date()
                    
                    status = str(row['License Status']).strip()
                    
                    # Skip if not Active (you might want to include Inactive too)
                    if status != 'Active':
                        results["skipped"] += 1
                        continue
                    
                    # Check if CPA already exists
                    existing_cpa = self.db.query(CPA).filter(
                        CPA.license_number == license_number
                    ).first()
                    
                    if existing_cpa:
                        # Update existing record
                        existing_cpa.full_name = full_name
                        existing_cpa.license_issue_date = issue_date
                        existing_cpa.license_expiration_date = expiration_date
                        existing_cpa.status = status
                        existing_cpa.last_oplc_sync = datetime.now()
                        results["updated"] += 1
                    else:
                        # Create new record
                        new_cpa = CPA(
                            license_number=license_number,
                            full_name=full_name,
                            license_issue_date=issue_date,
                            license_expiration_date=expiration_date,
                            status=status,
                            last_oplc_sync=datetime.now()
                        )
                        self.db.add(new_cpa)
                        results["created"] += 1
                        
                except Exception as e:
                    print(f"Error processing row {license_number}: {e}")
                    results["errors"] += 1
                    continue
            
            self.db.commit()
            return results
            
        except Exception as e:
            print(f"Error importing Excel file: {e}")
            self.db.rollback()
            return {"created": 0, "updated": 0, "errors": 1, "skipped": 0}
