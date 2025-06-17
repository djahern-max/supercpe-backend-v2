# app/services/nh_compliance.py - Enhanced NH CPA Compliance with Clarified Rules

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from app.models.cpa import CPA


@dataclass
class CompliancePeriod:
    """Represents a CPA's current compliance period with detailed explanations"""

    start_date: date
    end_date: date
    period_type: str  # "biennial"
    hours_required: int  # 80
    ethics_required: int  # 4
    annual_minimum: int  # 20
    days_remaining: int
    is_transition_period: bool

    # Enhanced explanatory fields
    license_category: str  # "existing_june_renewal", "new_anniversary_renewal"
    rule_explanation: str
    renewal_pattern: str
    cpe_breakdown: Dict[str, Any]


@dataclass
class ComplianceStatus:
    """Comprehensive compliance status with detailed explanations"""

    is_compliant: bool
    overall_status: str
    confidence_level: str  # "High", "Medium", "Low" based on data completeness

    # Progress tracking
    total_hours_completed: float
    total_hours_required: int
    ethics_hours_completed: float
    ethics_hours_required: int

    # Annual breakdown
    year1_hours: float
    year1_required: int
    year1_compliant: bool
    year2_hours: float
    year2_required: int
    year2_compliant: bool

    # Timeline and deadlines
    current_period: CompliancePeriod
    days_until_renewal: int
    next_renewal_date: date

    # Enhanced guidance
    personalized_explanation: str
    rule_category_explanation: str
    historical_context: str
    recommendations: List[str]
    next_actions: List[str]
    important_dates: List[Dict[str, Any]]


class EnhancedNHComplianceService:
    """
    Enhanced New Hampshire CPA Compliance Service
    Implements the clarified 2023 rule changes with detailed explanations
    """

    RULE_CHANGE_DATE = date(2023, 2, 22)  # When new system started

    def generate_comprehensive_dashboard(
        self, cpa: CPA, cpe_records: List[Any] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete, personalized compliance dashboard
        """
        if cpe_records is None:
            cpe_records = []

        # Calculate current period and status
        current_period = self.calculate_compliance_period(cpa)
        status = self.calculate_detailed_status(cpa, cpe_records, current_period)

        return {
            "cpa_profile": self._generate_cpa_profile(cpa),
            "license_analysis": self._analyze_license_history(cpa),
            "current_requirements": self._explain_current_requirements(
                cpa, current_period
            ),
            "compliance_status": status,
            "timeline": self._generate_compliance_timeline(cpa, current_period),
            "educational_content": self._generate_educational_content(
                cpa, current_period
            ),
            "action_plan": self._generate_action_plan(status),
            "historical_context": self._explain_rule_changes(cpa),
        }

    def calculate_compliance_period(
        self, cpa: CPA, check_date: Optional[date] = None
    ) -> CompliancePeriod:
        """Calculate compliance period with enhanced explanations"""
        if check_date is None:
            check_date = date.today()

        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date

        # Determine category based on license date
        if license_date <= self.RULE_CHANGE_DATE:
            return self._calculate_existing_cpa_period(cpa, check_date)
        else:
            return self._calculate_new_cpa_period(cpa, check_date)

    def _calculate_existing_cpa_period(
        self, cpa: CPA, check_date: date
    ) -> CompliancePeriod:
        """Existing CPAs (licensed before Feb 2023) - June 30 renewals, 2-year cycles"""
        expiration_date = cpa.license_expiration_date

        # Work backwards from expiration to find period start
        period_end = expiration_date
        period_start = period_end - relativedelta(years=2, days=-1)

        # Check if this spans the rule change
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
            license_category="existing_june_renewal",
            rule_explanation=f"As a CPA licensed before February 2023, you maintain June 30th renewal dates but are now on 2-year renewal cycles instead of the previous 3-year cycles.",
            renewal_pattern="June 30th every 2 years",
            cpe_breakdown={
                "total_required": 80,
                "ethics_required": 4,
                "annual_minimum": 20,
                "period_length": "2 years",
                "calculation": "20 hours minimum per year × 2 years = 40 hour minimum, with 80 hours total maximum",
            },
        )

    def _calculate_new_cpa_period(self, cpa: CPA, check_date: date) -> CompliancePeriod:
        """New CPAs (licensed after Feb 2023) - Anniversary renewals"""
        license_date = cpa.license_issue_date
        expiration_date = cpa.license_expiration_date

        period_start = license_date
        period_end = expiration_date
        days_remaining = (period_end - check_date).days

        renewal_month = license_date.strftime("%B")

        return CompliancePeriod(
            start_date=period_start,
            end_date=period_end,
            period_type="biennial",
            hours_required=80,
            ethics_required=4,
            annual_minimum=20,
            days_remaining=max(0, days_remaining),
            is_transition_period=False,
            license_category="new_anniversary_renewal",
            rule_explanation=f"As a CPA licensed after February 2023, your renewal follows your license anniversary date in {renewal_month}, with 2-year renewal cycles.",
            renewal_pattern=f"{renewal_month} every 2 years (anniversary-based)",
            cpe_breakdown={
                "total_required": 80,
                "ethics_required": 4,
                "annual_minimum": 20,
                "period_length": "2 years",
                "calculation": "20 hours minimum per year × 2 years = 40 hour minimum, with 80 hours total required",
            },
        )

    def _generate_cpa_profile(self, cpa: CPA) -> Dict[str, Any]:
        """Generate comprehensive CPA profile"""
        years_licensed = (date.today() - cpa.license_issue_date).days / 365.25

        return {
            "basic_info": {
                "license_number": cpa.license_number,
                "full_name": cpa.full_name,
                "status": cpa.status,
            },
            "license_timeline": {
                "issue_date": cpa.license_issue_date,
                "expiration_date": cpa.license_expiration_date,
                "years_licensed": round(years_licensed, 1),
                "license_age_category": (
                    "Veteran CPA"
                    if years_licensed > 10
                    else "Established CPA" if years_licensed > 5 else "Newer CPA"
                ),
            },
        }

    def _analyze_license_history(self, cpa: CPA) -> Dict[str, Any]:
        """Analyze when CPA was licensed relative to rule changes"""
        license_date = cpa.license_issue_date
        rule_change = self.RULE_CHANGE_DATE

        was_licensed_before_change = license_date <= rule_change

        if was_licensed_before_change:
            years_before_change = (rule_change - license_date).days / 365.25
            return {
                "category": "experienced_cpa",
                "licensed_before_rule_change": True,
                "years_before_change": round(years_before_change, 1),
                "explanation": f"You were licensed {round(years_before_change, 1)} years before the February 2023 rule changes, so you maintain June 30th renewal dates but now follow the new 2-year cycle requirements.",
                "transition_impact": "Converted from 3-year to 2-year renewal cycle, maintaining June 30th dates",
            }
        else:
            months_after_change = (license_date - rule_change).days / 30.44
            return {
                "category": "new_system_cpa",
                "licensed_before_rule_change": False,
                "months_after_change": round(months_after_change, 1),
                "explanation": f"You were licensed {round(months_after_change, 1)} months after the February 2023 rule changes, so you follow the new anniversary-based renewal system from the start.",
                "transition_impact": "Started directly on the new 2-year anniversary-based system",
            }

    def _explain_current_requirements(
        self, cpa: CPA, period: CompliancePeriod
    ) -> Dict[str, Any]:
        """Detailed explanation of current CPE requirements"""
        return {
            "summary": {
                "total_hours": period.hours_required,
                "ethics_hours": period.ethics_required,
                "annual_minimum": period.annual_minimum,
                "period_length": "2 years",
            },
            "detailed_breakdown": {
                "annual_requirement": {
                    "hours": 20,
                    "explanation": "You must complete at least 20 CPE hours each year, even in a 2-year cycle",
                },
                "total_requirement": {
                    "hours": 80,
                    "explanation": "Total of 80 CPE hours required over the 2-year period",
                },
                "ethics_requirement": {
                    "hours": 4,
                    "explanation": "4 hours of ethics CPE required once per 2-year period",
                },
            },
            "rule_comparison": {
                "previous_system": (
                    "120 hours over 3 years + 4 ethics"
                    if period.license_category == "existing_june_renewal"
                    else "N/A (started on new system)"
                ),
                "current_system": "80 hours over 2 years + 4 ethics",
                "improvement": "Reduced total hours and shorter renewal cycle",
            },
        }

    def _generate_compliance_timeline(
        self, cpa: CPA, period: CompliancePeriod
    ) -> Dict[str, Any]:
        """Generate visual timeline of compliance period"""
        total_days = (period.end_date - period.start_date).days
        elapsed_days = total_days - period.days_remaining
        progress_percentage = (elapsed_days / total_days * 100) if total_days > 0 else 0

        # Calculate key milestone dates
        quarter_mark = period.start_date + relativedelta(days=total_days // 4)
        half_mark = period.start_date + relativedelta(days=total_days // 2)
        three_quarter_mark = period.start_date + relativedelta(days=3 * total_days // 4)

        return {
            "period_overview": {
                "start_date": period.start_date,
                "end_date": period.end_date,
                "total_days": total_days,
                "days_remaining": period.days_remaining,
                "progress_percentage": round(progress_percentage, 1),
            },
            "milestones": [
                {
                    "date": quarter_mark,
                    "description": "25% through period - Good time for first annual minimum check",
                    "target_hours": 20,
                },
                {
                    "date": half_mark,
                    "description": "Halfway point - Should have at least 20 hours completed",
                    "target_hours": 40,
                },
                {
                    "date": three_quarter_mark,
                    "description": "75% through period - Focus on completing remaining hours",
                    "target_hours": 60,
                },
                {
                    "date": period.end_date,
                    "description": "Renewal deadline - All 80 hours + 4 ethics must be complete",
                    "target_hours": 80,
                },
            ],
            "urgency_level": (
                "Critical"
                if period.days_remaining <= 30
                else (
                    "High"
                    if period.days_remaining <= 90
                    else "Medium" if period.days_remaining <= 180 else "Low"
                )
            ),
        }

    def _generate_educational_content(
        self, cpa: CPA, period: CompliancePeriod
    ) -> Dict[str, Any]:
        """Generate educational content about NH CPE rules"""
        return {
            "key_facts": [
                "All NH CPAs are now on 2-year renewal cycles (RSA 310:8)",
                "Total requirement: 80 CPE hours over 2 years",
                "Annual minimum: 20 hours per year must be met",
                "Ethics requirement: 4 hours of ethics CPE per 2-year period",
                "Renewal dates: June 30th for pre-2023 CPAs, anniversary dates for newer CPAs",
            ],
            "common_questions": [
                {
                    "question": "Why did my renewal change from 3 years to 2 years?",
                    "answer": "RSA 310:8 standardized all NH professional licenses to 2-year terms. This applies to all CPAs, including those licensed before 2023.",
                },
                {
                    "question": "Do I still need 20 hours per year in a 2-year system?",
                    "answer": "Yes, the annual 20-hour minimum is still required each year, even within the 2-year cycle.",
                },
                {
                    "question": "How many ethics hours do I need?",
                    "answer": "4 hours of ethics CPE are required once per 2-year renewal period.",
                },
            ],
            "rule_changes_timeline": {
                "before_feb_2023": "3-year cycles, June 30th renewals for existing CPAs",
                "feb_2023_onwards": "2-year cycles for all CPAs, anniversary renewals for new licenses",
                "impact": "Reduced total hours (120→80) but shorter renewal periods (3→2 years)",
            },
        }

    def _generate_action_plan(self, status: ComplianceStatus) -> Dict[str, Any]:
        """Generate personalized action plan"""
        return {
            "immediate_actions": status.next_actions,
            "long_term_planning": status.recommendations,
            "suggested_schedule": self._suggest_cpe_schedule(status),
            "resources": {
                "nh_board_website": "https://www.nh.gov/accountancy/",
                "cpe_providers": [
                    "NHSCPA (New Hampshire Society of CPAs)",
                    "AICPA courses",
                    "University continuing education programs",
                    "Professional development organizations",
                ],
            },
        }

    def _suggest_cpe_schedule(self, status: ComplianceStatus) -> List[Dict[str, Any]]:
        """Suggest a CPE completion schedule"""
        remaining_hours = status.total_hours_required - status.total_hours_completed
        remaining_days = status.days_until_renewal

        if remaining_days <= 90:
            return [
                {
                    "period": "Immediately",
                    "suggestion": f"Complete all {remaining_hours} remaining hours ASAP",
                }
            ]

        monthly_target = remaining_hours / (remaining_days / 30.44)

        return [
            {
                "period": "Monthly target",
                "suggestion": f"Complete approximately {monthly_target:.1f} hours per month",
            },
            {
                "period": "Year 1 focus",
                "suggestion": "Ensure 20-hour annual minimum is met by anniversary",
            },
            {
                "period": "Ethics timing",
                "suggestion": "Complete 4 ethics hours anytime during the 2-year period",
            },
        ]

    def _explain_rule_changes(self, cpa: CPA) -> Dict[str, Any]:
        """Explain how rule changes affect this specific CPA"""
        was_licensed_before = cpa.license_issue_date <= self.RULE_CHANGE_DATE

        if was_licensed_before:
            return {
                "your_situation": "Existing CPA (licensed before February 2023)",
                "what_changed": [
                    "Renewal cycle reduced from 3 years to 2 years",
                    "Total CPE reduced from 120 hours to 80 hours",
                    "June 30th renewal date maintained",
                    "Annual 20-hour minimum still applies",
                ],
                "what_stayed_same": [
                    "June 30th renewal date",
                    "20 hours per year minimum requirement",
                    "4 hours ethics requirement",
                ],
                "transition_note": "You may have experienced one transition period where requirements were adjusted. All future renewals follow the standard 2-year, 80-hour pattern.",
            }
        else:
            return {
                "your_situation": "New system CPA (licensed after February 2023)",
                "what_applies": [
                    "2-year renewal cycles from the start",
                    "80 CPE hours per 2-year period",
                    "Anniversary-based renewal dates",
                    "20 hours minimum per year",
                ],
                "advantages": [
                    "Started on the simplified system",
                    "No transition period confusion",
                    "Consistent anniversary-based renewals",
                ],
                "renewal_pattern": f"Your license renews every {cpa.license_issue_date.strftime('%B')} (your anniversary month)",
            }

    def calculate_detailed_status(
        self, cpa: CPA, cpe_records: List[Any], period: CompliancePeriod
    ) -> ComplianceStatus:
        """Calculate detailed compliance status with enhanced explanations"""
        # Filter records for current period
        period_records = [
            record
            for record in cpe_records
            if period.start_date
            <= getattr(record, "completion_date", date.today())
            <= date.today()
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

        # Annual breakdown
        year1_start = period.start_date
        year1_end = year1_start + relativedelta(years=1, days=-1)
        year2_start = year1_end + relativedelta(days=1)

        year1_records = [
            r
            for r in period_records
            if year1_start <= getattr(r, "completion_date", date.today()) <= year1_end
        ]
        year2_records = [
            r
            for r in period_records
            if getattr(r, "completion_date", date.today()) >= year2_start
        ]

        year1_hours = sum(
            getattr(record, "cpe_credits", 0) or 0 for record in year1_records
        )
        year2_hours = sum(
            getattr(record, "cpe_credits", 0) or 0 for record in year2_records
        )

        # Compliance calculations
        is_compliant = (
            total_hours >= period.hours_required
            and ethics_hours >= period.ethics_required
            and year1_hours >= period.annual_minimum
            and year2_hours >= period.annual_minimum
        )

        # Generate status and explanations
        if len(cpe_records) == 0:
            overall_status = "Setup Required"
            confidence_level = "Low"
            personalized_explanation = "No CPE records found. Upload your certificates to get a complete compliance analysis."
        elif is_compliant:
            overall_status = "Compliant"
            confidence_level = "High" if len(period_records) > 5 else "Medium"
            personalized_explanation = f"You're on track! You've completed {total_hours:.1f} of {period.hours_required} required hours."
        else:
            overall_status = "Needs Attention"
            confidence_level = "Medium"
            missing = period.hours_required - total_hours
            personalized_explanation = f"You need {missing:.1f} more CPE hours to meet your {period.hours_required}-hour requirement."

        return ComplianceStatus(
            is_compliant=is_compliant,
            overall_status=overall_status,
            confidence_level=confidence_level,
            total_hours_completed=total_hours,
            total_hours_required=period.hours_required,
            ethics_hours_completed=ethics_hours,
            ethics_hours_required=period.ethics_required,
            year1_hours=year1_hours,
            year1_required=period.annual_minimum,
            year1_compliant=year1_hours >= period.annual_minimum,
            year2_hours=year2_hours,
            year2_required=period.annual_minimum,
            year2_compliant=year2_hours >= period.annual_minimum,
            current_period=period,
            days_until_renewal=period.days_remaining,
            next_renewal_date=period.end_date,
            personalized_explanation=personalized_explanation,
            rule_category_explanation=period.rule_explanation,
            historical_context=f"Licensed {cpa.license_issue_date.strftime('%B %Y')}, expires {period.end_date.strftime('%B %Y')}",
            recommendations=self._generate_enhanced_recommendations(
                period, total_hours, ethics_hours, year1_hours, year2_hours
            ),
            next_actions=self._generate_enhanced_actions(
                period, total_hours, ethics_hours
            ),
            important_dates=self._generate_important_dates(period),
        )

    def _generate_enhanced_recommendations(
        self,
        period: CompliancePeriod,
        total_hours: float,
        ethics_hours: float,
        year1_hours: float,
        year2_hours: float,
    ) -> List[str]:
        """Generate enhanced recommendations with specific guidance"""
        recommendations = []

        if total_hours < period.hours_required:
            needed = period.hours_required - total_hours
            recommendations.append(f"📚 Complete {needed:.1f} more general CPE hours")

        if ethics_hours < period.ethics_required:
            needed = period.ethics_required - ethics_hours
            recommendations.append(f"⚖️ Complete {needed:.1f} hours of ethics CPE")

        if year1_hours < period.annual_minimum:
            needed = period.annual_minimum - year1_hours
            recommendations.append(
                f"📅 Year 1: Complete {needed:.1f} more hours to meet annual minimum"
            )

        if year2_hours < period.annual_minimum:
            needed = period.annual_minimum - year2_hours
            recommendations.append(
                f"📅 Year 2: Complete {needed:.1f} more hours to meet annual minimum"
            )

        if period.days_remaining < 180:
            recommendations.append(
                "⏰ Consider accelerating CPE completion as renewal approaches"
            )

        return recommendations

    def _generate_enhanced_actions(
        self, period: CompliancePeriod, total_hours: float, ethics_hours: float
    ) -> List[str]:
        """Generate immediate action items"""
        actions = []

        if period.days_remaining <= 30:
            actions.append("🚨 URGENT: Renewal deadline in 30 days or less!")
        elif period.days_remaining <= 90:
            actions.append("⚠️ Important: Renewal deadline approaching in 3 months")

        if total_hours == 0:
            actions.append("📋 Start by uploading your existing CPE certificates")
        elif total_hours < period.hours_required / 2:
            actions.append("📈 Focus on completing more CPE hours")

        if ethics_hours == 0:
            actions.append("⚖️ Schedule ethics CPE courses (4 hours required)")

        return actions

    def _generate_important_dates(
        self, period: CompliancePeriod
    ) -> List[Dict[str, Any]]:
        """Generate list of important dates and deadlines"""
        dates = []

        # Renewal deadline
        dates.append(
            {
                "date": period.end_date,
                "event": "License Renewal Deadline",
                "description": f"All {period.hours_required} CPE hours must be completed",
                "importance": "Critical",
            }
        )

        # Annual minimums
        year1_end = period.start_date + relativedelta(years=1, days=-1)
        dates.append(
            {
                "date": year1_end,
                "event": "Year 1 Annual Minimum",
                "description": "20 CPE hours must be completed by this date",
                "importance": "High",
            }
        )

        # Warning dates
        if period.days_remaining > 90:
            warning_date = period.end_date - relativedelta(days=90)
            dates.append(
                {
                    "date": warning_date,
                    "event": "90-Day Warning",
                    "description": "Good time to ensure you're on track for renewal",
                    "importance": "Medium",
                }
            )

        return sorted(dates, key=lambda x: x["date"])


# API Integration Function
def get_enhanced_cpa_dashboard(
    cpa: CPA, cpe_records: List[Any] = None
) -> Dict[str, Any]:
    """Generate complete dashboard for API endpoint"""
    service = EnhancedNHComplianceService()
    return service.generate_comprehensive_dashboard(cpa, cpe_records or [])
