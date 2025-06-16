# app/services/time_window_compliance.py - CORRECTED Time Window Analysis Service

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from app.models.cpa import CPA

@dataclass
class TimeWindow:
    """Represents a specific compliance time window"""
    start_date: date
    end_date: date
    period_type: str  # "biennial", "triennial"
    hours_required: int
    ethics_required: int
    annual_minimum: int
    window_description: str
    is_historical: bool  # True if the window has already ended
    is_current: bool     # True if this is the current active period
    is_future: bool      # True if this window hasn't started yet

@dataclass
class WindowComplianceResult:
    """Results of analyzing a specific time window"""
    window: TimeWindow
    total_hours_found: float
    ethics_hours_found: float
    annual_breakdown: List[Dict[str, Any]]  # Year-by-year breakdown
    is_compliant: bool
    compliance_percentage: float
    missing_hours: float
    missing_ethics: float
    recommendations: List[str]
    can_upload_documents: bool  # True if user can upload docs for this period
    upload_deadline_passed: bool  # True if too late to upload for this period

class TimeWindowComplianceService:
    """
    Service for analyzing CPA compliance within specific time windows
    CORRECTED: Existing CPAs stay triennial until July 1, 2025
    """
    
    RULE_CHANGE_DATE = date(2023, 2, 22)
    EXISTING_CPA_BIENNIAL_START = date(2025, 7, 1)  # When existing CPAs switch to biennial
    
    def get_available_windows(self, cpa: CPA, check_date: Optional[date] = None) -> List[TimeWindow]:
        """
        Get all available compliance windows for a CPA
        CORRECTED: Proper transition handling
        """
        if check_date is None:
            check_date = date.today()
        
        windows = []
        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date
        
        # Determine if this is an existing CPA (pre-Feb 2023) or new CPA
        is_existing_cpa = license_date <= self.RULE_CHANGE_DATE
        
        if is_existing_cpa:
            windows.extend(self._get_existing_cpa_windows_corrected(cpa, check_date))
        else:
            windows.extend(self._get_new_cpa_windows(cpa, check_date))
        
        return sorted(windows, key=lambda w: w.end_date)
    
    def _get_existing_cpa_windows_corrected(self, cpa: CPA, check_date: date) -> List[TimeWindow]:
        """
        CORRECTED: Get windows for existing CPAs (licensed before Feb 2023)
        - Stay triennial until July 1, 2025
        - Switch to biennial starting July 1, 2025
        """
        windows = []
        expiration_date = cpa.license_expiration_date
        
        # Work backwards from current expiration to build windows
        current_end = expiration_date
        
        # Generate windows going back several periods
        for i in range(6):  # Cover more history
            if current_end >= self.EXISTING_CPA_BIENNIAL_START:
                # Biennial period (July 1, 2025 and after)
                period_start = current_end - relativedelta(years=2, days=-1)
                period_type = "biennial"
                hours_required = 80
                description_suffix = "(Biennial - New System)"
            else:
                # Triennial period (before July 1, 2025)
                period_start = current_end - relativedelta(years=3, days=-1)
                period_type = "triennial"
                hours_required = 120
                description_suffix = "(Triennial - Old System)"
            
            # Determine status
            is_historical = current_end < check_date
            is_current = period_start <= check_date <= current_end
            is_future = period_start > check_date
            
            # Create description
            if is_current:
                description = f"Current Period: {period_start.strftime('%b %Y')} - {current_end.strftime('%b %Y')} {description_suffix}"
            elif is_future:
                description = f"Next Period: {period_start.strftime('%b %Y')} - {current_end.strftime('%b %Y')} {description_suffix}"
            else:
                description = f"Historical Period: {period_start.strftime('%b %Y')} - {current_end.strftime('%b %Y')} {description_suffix}"
            
            windows.append(TimeWindow(
                start_date=period_start,
                end_date=current_end,
                period_type=period_type,
                hours_required=hours_required,
                ethics_required=4,
                annual_minimum=20,
                window_description=description,
                is_historical=is_historical,
                is_current=is_current,
                is_future=is_future
            ))
            
            # Move to previous period
            current_end = period_start - relativedelta(days=1)
            
            # Stop if we go too far back
            if current_end < cpa.license_issue_date:
                break
        
        return windows
    
    def _get_new_cpa_windows(self, cpa: CPA, check_date: date) -> List[TimeWindow]:
        """Get windows for new CPAs (licensed after Feb 2023) - always biennial"""
        windows = []
        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date
        
        # For new CPAs, all periods are 2-year from the start
        current_start = license_date
        period_count = 0
        
        while current_start <= expiration_date and period_count < 5:
            period_end = min(current_start + relativedelta(years=2, days=-1), expiration_date)
            
            is_historical = period_end < check_date
            is_current = current_start <= check_date <= period_end
            is_future = current_start > check_date
            
            if is_current:
                description = f"Current Period: {current_start.strftime('%b %Y')} - {period_end.strftime('%b %Y')} (Biennial)"
            elif is_future:
                description = f"Future Period: {current_start.strftime('%b %Y')} - {period_end.strftime('%b %Y')} (Biennial)"
            else:
                description = f"Period {period_count + 1}: {current_start.strftime('%b %Y')} - {period_end.strftime('%b %Y')} (Biennial)"
            
            windows.append(TimeWindow(
                start_date=current_start,
                end_date=period_end,
                period_type="biennial",
                hours_required=80,
                ethics_required=4,
                annual_minimum=20,
                window_description=description,
                is_historical=is_historical,
                is_current=is_current,
                is_future=is_future
            ))
            
            current_start = period_end + relativedelta(days=1)
            period_count += 1
        
        return windows
    
    def analyze_window(self, cpa: CPA, window: TimeWindow, cpe_records: List[Any]) -> WindowComplianceResult:
        """
        Analyze compliance for a specific time window
        """
        # Filter CPE records for this window
        window_records = [
            record for record in cpe_records 
            if window.start_date <= getattr(record, 'completion_date', date.min) <= window.end_date
        ]
        
        # Calculate totals
        total_hours = sum(getattr(record, 'cpe_credits', 0) or 0 for record in window_records)
        ethics_hours = sum(
            getattr(record, 'cpe_credits', 0) or 0 
            for record in window_records 
            if getattr(record, 'is_ethics', False)
        )
        
        # Annual breakdown
        annual_breakdown = []
        current_year_start = window.start_date
        year_number = 1
        
        years_in_period = 3 if window.period_type == "triennial" else 2
        
        for year in range(years_in_period):
            year_end = min(
                current_year_start + relativedelta(years=1, days=-1),
                window.end_date
            )
            
            year_records = [
                r for r in window_records 
                if current_year_start <= getattr(r, 'completion_date', date.min) <= year_end
            ]
            year_hours = sum(getattr(r, 'cpe_credits', 0) or 0 for r in year_records)
            
            annual_breakdown.append({
                "year": year_number,
                "start_date": current_year_start,
                "end_date": year_end,
                "hours_completed": year_hours,
                "hours_required": window.annual_minimum,
                "is_compliant": year_hours >= window.annual_minimum
            })
            
            current_year_start = year_end + relativedelta(days=1)
            year_number += 1
            
            if current_year_start > window.end_date:
                break
        
        # Compliance calculations
        is_compliant = (
            total_hours >= window.hours_required and
            ethics_hours >= window.ethics_required and
            all(year["is_compliant"] for year in annual_breakdown)
        )
        
        compliance_percentage = min(100, (total_hours / window.hours_required) * 100)
        missing_hours = max(0, window.hours_required - total_hours)
        missing_ethics = max(0, window.ethics_required - ethics_hours)
        
        # Recommendations
        recommendations = []
        if missing_hours > 0:
            recommendations.append(f"Need {missing_hours:.1f} more general CPE hours")
        if missing_ethics > 0:
            recommendations.append(f"Need {missing_ethics:.1f} more ethics hours")
        
        for year in annual_breakdown:
            if not year["is_compliant"]:
                shortage = year["hours_required"] - year["hours_completed"]
                recommendations.append(f"Year {year['year']} shortage: {shortage:.1f} hours")
        
        if is_compliant:
            recommendations.append("✅ Fully compliant for this period!")
        
        # Upload eligibility
        today = date.today()
        can_upload_documents = True  # Always allow uploads for analysis
        upload_deadline_passed = window.is_historical and (today - window.end_date).days > 365
        
        return WindowComplianceResult(
            window=window,
            total_hours_found=total_hours,
            ethics_hours_found=ethics_hours,
            annual_breakdown=annual_breakdown,
            is_compliant=is_compliant,
            compliance_percentage=compliance_percentage,
            missing_hours=missing_hours,
            missing_ethics=missing_ethics,
            recommendations=recommendations,
            can_upload_documents=can_upload_documents,
            upload_deadline_passed=upload_deadline_passed
        )
