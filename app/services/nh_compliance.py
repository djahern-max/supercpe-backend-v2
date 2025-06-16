# app/services/nh_compliance.py - NH CPA Compliance Logic

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from app.models.cpa import CPA


@dataclass
class CompliancePeriod:
    """Represents a CPA's current compliance period"""

    start_date: date
    end_date: date
    period_type: str  # "biennial"
    hours_required: int  # 80
    ethics_required: int  # 4
    annual_minimum: int  # 20
    days_remaining: int
    is_transition_period: bool  # True if this period spans the rule change


@dataclass
class ComplianceStatus:
    """Current compliance status for a CPA"""

    is_compliant: bool
    overall_status: str  # "Compliant", "At Risk", "Non-Compliant", "Needs Setup"

    # Progress tracking
    total_hours_completed: float
    total_hours_required: int
    ethics_hours_completed: float
    ethics_hours_required: int

    # Annual minimums (for 2-year period)
    year1_hours: float
    year1_required: int  # 20
    year1_compliant: bool
    year2_hours: float
    year2_required: int  # 20
    year2_compliant: bool

    # Timeline
    current_period: CompliancePeriod
    days_until_renewal: int

    # Recommendations
    recommendations: List[str]
    next_actions: List[str]


class NHComplianceService:
    """
    New Hampshire CPA Compliance Service
    Handles the complex NH compliance rules including the 2023 transition
    """

    # Rule change date - when new 2-year system started
    RULE_CHANGE_DATE = date(2023, 2, 22)

    def calculate_compliance_period(
        self, cpa: CPA, check_date: Optional[date] = None
    ) -> CompliancePeriod:
        """
        Calculate the current compliance period for a CPA

        Rules:
        1. All CPAs are now on 2-year cycles (80 hours + 4 ethics)
        2. Licensed before Feb 2023: Keep June 30 renewal dates
        3. Licensed after Feb 2023: Anniversary month renewals
        4. 20 hours minimum per year
        """
        if check_date is None:
            check_date = date.today()

        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date

        # Determine period type based on license date
        if license_date <= self.RULE_CHANGE_DATE:
            # Existing CPA - June 30 renewals, but now 2-year periods
            return self._calculate_existing_cpa_period(cpa, check_date)
        else:
            # New CPA - Anniversary renewals
            return self._calculate_new_cpa_period(cpa, check_date)

    def _calculate_existing_cpa_period(
        self, cpa: CPA, check_date: date
    ) -> CompliancePeriod:
        """
        Existing CPAs (licensed before Feb 2023)
        - Keep June 30 renewal dates
        - Now on 2-year cycles instead of 3-year
        """
        expiration_date = cpa.license_expiration_date

        # Work backwards from expiration to find period start
        # All existing CPAs renew on June 30, every 2 years now
        period_end = expiration_date
        period_start = period_end - relativedelta(
            years=2, days=-1
        )  # 2 years minus 1 day

        # Check if this period spans the rule change (transition period)
        is_transition = period_start <= self.RULE_CHANGE_DATE <= period_end

        days_remaining = (period_end - check_date).days

        return CompliancePeriod(
            start_date=period_start,
            end_date=period_end,
            period_type="biennial",
            hours_required=80,
            ethics_required=4,
            annual_minimum=20,
            days_remaining=max(0, days_remaining),
            is_transition_period=is_transition,
        )

    def _calculate_new_cpa_period(self, cpa: CPA, check_date: date) -> CompliancePeriod:
        """
        New CPAs (licensed after Feb 2023)
        - Anniversary month renewals
        - 2-year periods from license date
        """
        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date

        # For new CPAs, the period aligns with their license anniversary
        period_start = license_date
        period_end = expiration_date

        days_remaining = (period_end - check_date).days

        return CompliancePeriod(
            start_date=period_start,
            end_date=period_end,
            period_type="biennial",
            hours_required=80,
            ethics_required=4,
            annual_minimum=20,
            days_remaining=max(0, days_remaining),
            is_transition_period=False,  # New CPAs start clean
        )

    def calculate_compliance_status(
        self, cpa: CPA, cpe_records: List[Any]
    ) -> ComplianceStatus:
        """
        Calculate detailed compliance status for a CPA
        """
        current_period = self.calculate_compliance_period(cpa)

        # Filter CPE records for current period
        period_records = [
            record
            for record in cpe_records
            if current_period.start_date <= record.completion_date <= date.today()
        ]

        # Calculate totals
        total_hours = sum(
            getattr(record, "cpe_credits", 0) or 0 for record in period_records
        )
        ethics_hours = sum(
            getattr(record, "cpe_credits", 0) or 0
            for record in period_records
            if getattr(record, "is_ethics", False)
        )

        # Calculate annual breakdown
        year1_start = current_period.start_date
        year1_end = year1_start + relativedelta(years=1, days=-1)
        year2_start = year1_end + relativedelta(days=1)
        year2_end = current_period.end_date

        year1_records = [
            r for r in period_records if year1_start <= r.completion_date <= year1_end
        ]
        year2_records = [
            r for r in period_records if year2_start <= r.completion_date <= year2_end
        ]

        year1_hours = sum(getattr(r, "cpe_credits", 0) or 0 for r in year1_records)
        year2_hours = sum(getattr(r, "cpe_credits", 0) or 0 for r in year2_records)

        # Compliance checks
        is_compliant = (
            total_hours >= current_period.hours_required
            and ethics_hours >= current_period.ethics_required
            and year1_hours >= current_period.annual_minimum
            and year2_hours >= current_period.annual_minimum
        )

        year1_compliant = year1_hours >= current_period.annual_minimum
        year2_compliant = year2_hours >= current_period.annual_minimum

        # Determine overall status
        if is_compliant:
            overall_status = "Compliant"
        elif current_period.days_remaining <= 30:
            overall_status = "Critical"
        elif total_hours >= current_period.hours_required * 0.8:
            overall_status = "At Risk"
        else:
            overall_status = "Non-Compliant"

        # Generate recommendations
        recommendations = self._generate_recommendations(
            current_period, total_hours, ethics_hours, year1_hours, year2_hours
        )

        next_actions = self._generate_next_actions(
            current_period, total_hours, ethics_hours, year1_compliant, year2_compliant
        )

        return ComplianceStatus(
            is_compliant=is_compliant,
            overall_status=overall_status,
            total_hours_completed=total_hours,
            total_hours_required=current_period.hours_required,
            ethics_hours_completed=ethics_hours,
            ethics_hours_required=current_period.ethics_required,
            year1_hours=year1_hours,
            year1_required=current_period.annual_minimum,
            year1_compliant=year1_compliant,
            year2_hours=year2_hours,
            year2_required=current_period.annual_minimum,
            year2_compliant=year2_compliant,
            current_period=current_period,
            days_until_renewal=current_period.days_remaining,
            recommendations=recommendations,
            next_actions=next_actions,
        )

    def _generate_recommendations(
        self,
        period: CompliancePeriod,
        total_hours: float,
        ethics_hours: float,
        year1_hours: float,
        year2_hours: float,
    ) -> List[str]:
        """Generate specific recommendations based on compliance gaps"""
        recommendations = []

        # Total hours check
        if total_hours < period.hours_required:
            needed = period.hours_required - total_hours
            recommendations.append(
                f"Complete {needed:.1f} more CPE hours before {period.end_date}"
            )

        # Ethics check
        if ethics_hours < period.ethics_required:
            needed = period.ethics_required - ethics_hours
            recommendations.append(f"Complete {needed:.1f} more ethics hours")

        # Annual minimums
        if year1_hours < period.annual_minimum:
            needed = period.annual_minimum - year1_hours
            recommendations.append(f"Year 1 shortfall: Need {needed:.1f} more hours")

        if year2_hours < period.annual_minimum:
            needed = period.annual_minimum - year2_hours
            recommendations.append(f"Year 2 shortfall: Need {needed:.1f} more hours")

        # Transition period guidance
        if period.is_transition_period:
            recommendations.append(
                "Note: This period spans the 2023 rule change. Requirements are now 80 hours (not 120) for 2-year periods."
            )

        return recommendations

    def _generate_next_actions(
        self,
        period: CompliancePeriod,
        total_hours: float,
        ethics_hours: float,
        year1_compliant: bool,
        year2_compliant: bool,
    ) -> List[str]:
        """Generate immediate next actions"""
        actions = []

        if period.days_remaining <= 30:
            actions.append("🚨 URGENT: Renewal deadline approaching!")

        if total_hours < period.hours_required:
            if period.days_remaining <= 60:
                actions.append("Focus on completing general CPE hours immediately")
            else:
                actions.append(
                    "Plan to complete remaining CPE hours over the next few months"
                )

        if ethics_hours < period.ethics_required:
            actions.append("Schedule ethics CPE courses (4 hours required)")

        if not year1_compliant or not year2_compliant:
            actions.append("Review annual minimum requirements (20 hours per year)")

        if not actions:
            actions.append("✅ You're on track! Continue current CPE schedule.")

        return actions


# Example usage functions for API endpoints
def get_cpa_compliance_dashboard(cpa: CPA, cpe_records: List[Any]) -> Dict[str, Any]:
    """Generate dashboard data for a CPA"""
    service = NHComplianceService()
    status = service.calculate_compliance_status(cpa, cpe_records)

    return {
        "cpa_info": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name,
            "license_issue_date": cpa.license_issue_date,
            "license_expiration_date": cpa.license_expiration_date,
        },
        "compliance": {
            "is_compliant": status.is_compliant,
            "overall_status": status.overall_status,
            "days_until_renewal": status.days_until_renewal,
        },
        "progress": {
            "total_hours": f"{status.total_hours_completed:.1f}/{status.total_hours_required}",
            "ethics_hours": f"{status.ethics_hours_completed:.1f}/{status.ethics_hours_required}",
            "year1_hours": f"{status.year1_hours:.1f}/{status.year1_required}",
            "year2_hours": f"{status.year2_hours:.1f}/{status.year2_required}",
        },
        "period_info": {
            "period_start": status.current_period.start_date,
            "period_end": status.current_period.end_date,
            "is_transition_period": status.current_period.is_transition_period,
        },
        "recommendations": status.recommendations,
        "next_actions": status.next_actions,
    }
