"""
Trial Management Service - Smart Trial System for SaaS.

Implements best practices from leading SaaS companies:
- Time-based limits (14 days)
- Usage-based limits (reports, templates, files)
- Daily usage caps to prevent "one-day sprint" abuse
- Progressive feature unlocking
- Automatic conversion reminders
"""
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from src.api.models.models import User, SubscriptionTier, ReportTemplate

logger = logging.getLogger(__name__)


class TrialService:
    """
    Manages trial periods with anti-abuse mechanisms.
    
    Best practices implemented:
    1. 14-day trial period (industry standard)
    2. Usage limits to prevent abuse:
       - Max 10 reports total during trial
       - Max 3 saved templates
       - Max 5 file uploads
    3. Daily caps to encourage multi-day engagement:
       - Max 3 reports per day
       - Resets automatically at midnight
    4. Feature gating based on trial status
    """
    
    # Trial configuration (can be moved to config)
    TRIAL_DURATION_DAYS = 14
    MAX_REPORTS_TRIAL = 10
    MAX_TEMPLATES_TRIAL = 3
    MAX_FILES_TRIAL = 5
    MAX_REPORTS_PER_DAY = 3  # Anti-abuse: prevent one-day sprint
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def start_trial(self, user: User) -> Dict[str, Any]:
        """
        Initialize trial for a new user.
        
        Returns:
            Dict with trial info and limitations
        """
        now = datetime.utcnow()
        trial_end = now + timedelta(days=self.TRIAL_DURATION_DAYS)
        
        user.subscription_tier = SubscriptionTier.TRIAL
        user.trial_started_at = now
        user.trial_ends_at = trial_end
        user.max_reports_trial = self.MAX_REPORTS_TRIAL
        user.max_templates_trial = self.MAX_TEMPLATES_TRIAL
        user.max_files_trial = self.MAX_FILES_TRIAL
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Trial started for user {user.id}, ends at {trial_end}")
        
        return {
            "status": "trial",
            "trial_started_at": now.isoformat(),
            "trial_ends_at": trial_end.isoformat(),
            "days_remaining": self.TRIAL_DURATION_DAYS,
            "limits": {
                "reports_total": self.MAX_REPORTS_TRIAL,
                "templates": self.MAX_TEMPLATES_TRIAL,
                "files": self.MAX_FILES_TRIAL,
                "reports_per_day": self.MAX_REPORTS_PER_DAY
            },
            "message": f"Welcome! You have {self.TRIAL_DURATION_DAYS} days of free trial."
        }
    
    async def check_trial_status(self, user: User) -> Dict[str, Any]:
        """
        Check if trial is still valid and within limits.
        
        Returns:
            Dict with status, remaining limits, and any warnings
        """
        now = datetime.utcnow()
        today = date.today()
        
        # Check if trial has expired
        if user.trial_ends_at and now > user.trial_ends_at:
            return {
                "is_valid": False,
                "reason": "trial_expired",
                "message": "Your trial period has ended. Please upgrade to continue.",
                "expired_at": user.trial_ends_at.isoformat()
            }
        
        # Check total report limit
        if user.reports_generated_count >= user.max_reports_trial:
            return {
                "is_valid": False,
                "reason": "report_limit_reached",
                "message": f"You've generated {user.reports_generated_count} reports (trial limit: {user.max_reports_trial}). Upgrade for unlimited reports.",
                "current": user.reports_generated_count,
                "limit": user.max_reports_trial
            }
        
        # Check template limit
        if user.templates_saved_count >= user.max_templates_trial:
            return {
                "is_valid": False,
                "reason": "template_limit_reached",
                "message": f"You've saved {user.templates_saved_count} templates (trial limit: {user.max_templates_trial}). Upgrade for more.",
                "current": user.templates_saved_count,
                "limit": user.max_templates_trial
            }
        
        # Check file upload limit
        if user.files_uploaded_count >= user.max_files_trial:
            return {
                "is_valid": False,
                "reason": "file_limit_reached",
                "message": f"You've uploaded {user.files_uploaded_count} files (trial limit: {user.max_files_trial}). Upgrade for more.",
                "current": user.files_uploaded_count,
                "limit": user.max_files_trial
            }
        
        # Check daily report limit (anti-abuse)
        daily_limit_reached = await self._check_daily_report_limit(user)
        if daily_limit_reached:
            return {
                "is_valid": True,  # Trial is valid, but daily cap hit
                "daily_cap_reached": True,
                "message": f"You've reached the daily limit of {self.MAX_REPORTS_PER_DAY} reports. Come back tomorrow or upgrade now!",
                "resets_at": "midnight UTC"
            }
        
        # Trial is valid
        days_remaining = (user.trial_ends_at - now).days if user.trial_ends_at else 0
        
        return {
            "is_valid": True,
            "status": "trial",
            "days_remaining": days_remaining,
            "usage": {
                "reports_generated": user.reports_generated_count,
                "reports_limit": user.max_reports_trial,
                "templates_saved": user.templates_saved_count,
                "templates_limit": user.max_templates_trial,
                "files_uploaded": user.files_uploaded_count,
                "files_limit": user.max_files_trial,
                "daily_reports": user.daily_report_count,
                "daily_limit": self.MAX_REPORTS_PER_DAY
            },
            "warnings": self._get_trial_warnings(user, days_remaining)
        }
    
    async def _check_daily_report_limit(self, user: User) -> bool:
        """Check if user has reached daily report limit."""
        today = date.today()
        
        # Reset daily counter if it's a new day
        if user.daily_report_reset_date != today:
            user.daily_report_count = 0
            user.daily_report_reset_date = today
            await self.db.commit()
        
        return user.daily_report_count >= self.MAX_REPORTS_PER_DAY
    
    async def increment_report_count(self, user: User) -> Tuple[bool, str]:
        """
        Increment report generation counter.
        
        Returns:
            (success, message)
        """
        # First check overall trial status
        status = await self.check_trial_status(user)
        
        if not status["is_valid"] and not status.get("daily_cap_reached"):
            return False, status["message"]
        
        if status.get("daily_cap_reached"):
            return False, status["message"]
        
        # Increment counters
        user.reports_generated_count += 1
        user.daily_report_count += 1
        user.last_report_generated_at = datetime.utcnow()
        
        # Update reset date if needed
        today = date.today()
        if user.daily_report_reset_date != today:
            user.daily_report_count = 1
            user.daily_report_reset_date = today
        
        await self.db.commit()
        
        remaining = user.max_reports_trial - user.reports_generated_count
        daily_remaining = self.MAX_REPORTS_PER_DAY - user.daily_report_count
        
        return True, f"Report generated. {remaining} reports remaining in trial. {daily_remaining} reports remaining today."
    
    async def increment_template_count(self, user: User) -> Tuple[bool, str]:
        """Increment saved template counter."""
        status = await self.check_trial_status(user)
        
        if not status["is_valid"]:
            return False, status["message"]
        
        user.templates_saved_count += 1
        await self.db.commit()
        
        remaining = user.max_templates_trial - user.templates_saved_count
        return True, f"Template saved. {remaining} templates remaining in trial."
    
    async def increment_file_count(self, user: User) -> Tuple[bool, str]:
        """Increment file upload counter."""
        status = await self.check_trial_status(user)
        
        if not status["is_valid"]:
            return False, status["message"]
        
        user.files_uploaded_count += 1
        await self.db.commit()
        
        remaining = user.max_files_trial - user.files_uploaded_count
        return True, f"File uploaded. {remaining} files remaining in trial."
    
    def _get_trial_warnings(self, user: User, days_remaining: int) -> list:
        """Generate warnings for trial expiration approaching."""
        warnings = []
        
        if days_remaining <= 3:
            warnings.append(f"⚠️ Your trial ends in {days_remaining} days! Upgrade now to avoid interruption.")
        
        if user.reports_generated_count >= user.max_reports_trial * 0.8:
            warnings.append(f"⚠️ You've used {user.reports_generated_count}/{user.max_reports_trial} reports. Consider upgrading soon.")
        
        return warnings
    
    async def upgrade_to_paid(self, user: User, tier: SubscriptionTier) -> Dict[str, Any]:
        """
        Convert trial user to paid subscription.
        
        Args:
            user: User to upgrade
            tier: Subscription tier (BASIC, PRO, ENTERPRISE)
        
        Returns:
            Confirmation dict
        """
        now = datetime.utcnow()
        
        # Set subscription
        user.subscription_tier = tier
        user.subscription_expires_at = now + timedelta(days=365)  # 1 year
        
        # Remove trial limits
        user.max_reports_trial = 999999  # Effectively unlimited
        user.max_templates_trial = 999999
        user.max_files_trial = 999999
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"User {user.id} upgraded to {tier.value}")
        
        return {
            "status": "success",
            "tier": tier.value,
            "expires_at": user.subscription_expires_at.isoformat(),
            "message": f"Successfully upgraded to {tier.value.capitalize()} plan!"
        }
    
    def get_feature_limits(self, tier: SubscriptionTier) -> Dict[str, Any]:
        """Get feature limits for each subscription tier."""
        limits = {
            SubscriptionTier.FREE: {
                "reports_per_month": 5,
                "templates": 1,
                "files": 2,
                "export_formats": ["pdf"],
                "support": "community"
            },
            SubscriptionTier.TRIAL: {
                "reports_total": self.MAX_REPORTS_TRIAL,
                "templates": self.MAX_TEMPLATES_TRIAL,
                "files": self.MAX_FILES_TRIAL,
                "reports_per_day": self.MAX_REPORTS_PER_DAY,
                "export_formats": ["pdf", "pptx"],
                "support": "email",
                "duration_days": self.TRIAL_DURATION_DAYS
            },
            SubscriptionTier.BASIC: {
                "reports_per_month": 50,
                "templates": 10,
                "files": 20,
                "export_formats": ["pdf", "pptx", "xlsx"],
                "support": "email",
                "price_monthly": 990
            },
            SubscriptionTier.PRO: {
                "reports_per_month": 200,
                "templates": 50,
                "files": 100,
                "export_formats": ["pdf", "pptx", "xlsx", "api"],
                "support": "priority",
                "ai_features": True,
                "price_monthly": 2990
            },
            SubscriptionTier.ENTERPRISE: {
                "reports_per_month": -1,  # Unlimited
                "templates": -1,
                "files": -1,
                "export_formats": ["pdf", "pptx", "xlsx", "api", "webhook"],
                "support": "dedicated",
                "ai_features": True,
                "custom_integrations": True,
                "sla": True,
                "price_monthly": 9990
            }
        }
        
        return limits.get(tier, limits[SubscriptionTier.FREE])


# Helper function to get trial service
def get_trial_service(db: AsyncSession) -> TrialService:
    """Dependency injection for TrialService."""
    return TrialService(db)
