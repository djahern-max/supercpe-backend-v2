#!/usr/bin/env python3
"""
Standalone script to import CPA data from OPLC Excel files
This replaces the admin endpoint functionality
"""

import sys
import os
from pathlib import Path
import argparse
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.core.config import settings


def import_cpa_file(file_path: str, dry_run: bool = False) -> dict:
    """Import CPA data from Excel file"""

    # Validate file exists and is Excel
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.lower().endswith((".xlsx", ".xls")):
        raise ValueError("File must be Excel format (.xlsx or .xls)")

    # Get database session
    db = next(get_db())

    try:
        print(
            f"🔄 {'DRY RUN: ' if dry_run else ''}Importing CPA data from: {file_path}"
        )
        print(f"📊 Database: {settings.database_url}")
        print(f"⏰ Started at: {datetime.now()}")
        print("-" * 50)

        # Create import service
        import_service = CPAImportService(db)

        if dry_run:
            print("⚠️  DRY RUN MODE - No changes will be saved to database")
            # For dry run, we'd need to add this functionality to CPAImportService
            # For now, just show what would happen
            results = {
                "message": "Dry run not yet implemented - would import from file"
            }
        else:
            # Actually import the data
            results = import_service.import_from_excel(file_path)

        # Display results
        print("\n📋 Import Results:")
        print(f"   ✅ Created: {results.get('created', 0)} new CPAs")
        print(f"   🔄 Updated: {results.get('updated', 0)} existing CPAs")
        print(f"   ⚠️  Errors:  {results.get('errors', 0)}")
        print(f"   ⏭️  Skipped: {results.get('skipped', 0)} (inactive licenses)")

        total_processed = results.get("created", 0) + results.get("updated", 0)
        print(f"\n🎯 Total CPAs processed: {total_processed}")

        if results.get("errors", 0) > 0:
            print("⚠️  Some errors occurred during import. Check logs for details.")

        return results

    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def get_database_stats():
    """Get current database statistics"""
    db = next(get_db())

    try:
        from app.models.cpa import CPA

        total_cpas = db.query(CPA).count()
        active_cpas = db.query(CPA).filter(CPA.status == "Active").count()
        recent_sync = db.query(CPA).filter(CPA.last_oplc_sync.isnot(None)).count()

        print("📊 Current Database Stats:")
        print(f"   Total CPAs: {total_cpas}")
        print(f"   Active CPAs: {active_cpas}")
        print(f"   Recently synced: {recent_sync}")

        # Show latest sync date
        latest_sync = (
            db.query(CPA.last_oplc_sync)
            .filter(CPA.last_oplc_sync.isnot(None))
            .order_by(CPA.last_oplc_sync.desc())
            .first()
        )

        if latest_sync and latest_sync[0]:
            print(f"   Latest sync: {latest_sync[0]}")

        return {
            "total": total_cpas,
            "active": active_cpas,
            "synced": recent_sync,
            "latest_sync": latest_sync[0] if latest_sync else None,
        }

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Import CPA data from OPLC Excel files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python import_cpa_data.py import monthly_cpas.xlsx
  python import_cpa_data.py import --dry-run monthly_cpas.xlsx
  python import_cpa_data.py stats
  
Monthly Process:
  1. Download latest OPLC Excel file
  2. Run: python import_cpa_data.py import path/to/file.xlsx
  3. Verify results and commit to git if needed
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Import command
    import_parser = subparsers.add_parser(
        "import", help="Import CPA data from Excel file"
    )
    import_parser.add_argument("file", help="Path to Excel file")
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes",
    )

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Show current database statistics"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "import":
            results = import_cpa_file(args.file, dry_run=args.dry_run)

            if not args.dry_run:
                print(f"\n✅ Import completed successfully!")
                print(f"💡 Tip: Check the results and commit any code changes to git")

        elif args.command == "stats":
            get_database_stats()

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
