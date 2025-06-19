# app/services/user_service.py - Safe user deletion with token cleanup
from sqlalchemy.orm import Session
from app.models.user import User
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user operations safely"""

    def __init__(self, db: Session):
        self.db = db

    def soft_delete_user(self, user_id: int, reason: str = "Admin deletion") -> bool:
        """
        Safely deactivate a user account (recommended over hard deletion)
        This preserves data integrity while preventing access
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()

            if not user:
                logger.warning(f"Attempted to delete non-existent user ID: {user_id}")
                return False

            # Store original email for logging
            original_email = user.email

            # Deactivate the user
            user.is_active = False

            # Clear all authentication tokens
            user.oauth_access_token = None
            user.oauth_refresh_token = None
            user.oauth_token_expires = None

            # Add deletion timestamp and reason
            user.updated_at = datetime.utcnow()
            # You might want to add these fields to your User model:
            # user.deleted_at = datetime.utcnow()
            # user.deletion_reason = reason

            self.db.commit()

            logger.info(
                f"User soft deleted: {original_email} (ID: {user_id}), Reason: {reason}"
            )
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to soft delete user {user_id}: {str(e)}")
            raise

    def hard_delete_user(self, user_id: int, reason: str = "Admin deletion") -> bool:
        """
        Permanently delete a user (use with caution!)
        This should be called after soft deletion if absolutely necessary
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()

            if not user:
                logger.warning(f"Attempted to delete non-existent user ID: {user_id}")
                return False

            # Store info for logging before deletion
            original_email = user.email
            original_license = user.license_number

            # Clear OAuth tokens first (important for security)
            user.oauth_access_token = None
            user.oauth_refresh_token = None
            user.oauth_token_expires = None
            self.db.commit()

            # Log the deletion before removing
            logger.warning(
                f"HARD DELETE - User: {original_email} (ID: {user_id}), License: {original_license}, Reason: {reason}"
            )

            # Actually delete the user
            self.db.delete(user)
            self.db.commit()

            logger.info(
                f"User hard deleted successfully: {original_email} (ID: {user_id})"
            )
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to hard delete user {user_id}: {str(e)}")
            raise

    def reactivate_user(self, user_id: int) -> bool:
        """Reactivate a soft-deleted user"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()

            if not user:
                logger.warning(
                    f"Attempted to reactivate non-existent user ID: {user_id}"
                )
                return False

            user.is_active = True
            user.updated_at = datetime.utcnow()
            # user.deleted_at = None  # Clear deletion timestamp if you have this field

            self.db.commit()

            logger.info(f"User reactivated: {user.email} (ID: {user_id})")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reactivate user {user_id}: {str(e)}")
            raise

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email, including inactive users"""
        return self.db.query(User).filter(User.email == email).first()

    def get_active_user_by_email(self, email: str) -> Optional[User]:
        """Get only active users by email"""
        return (
            self.db.query(User)
            .filter(User.email == email, User.is_active == True)
            .first()
        )


# Example admin endpoint that uses safe deletion
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db

admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])


@admin_router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    reason: str = "Admin action",
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user)  # Add admin check
):
    """Safely deactivate a user account"""

    # TODO: Add admin permission check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    user_service = UserService(db)

    try:
        success = user_service.soft_delete_user(user_id, reason)

        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "success": True,
            "message": f"User {user_id} deactivated successfully",
            "action": "soft_delete",
            "reason": reason,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to deactivate user: {str(e)}"
        )


@admin_router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user)  # Add admin check
):
    """Reactivate a deactivated user account"""

    user_service = UserService(db)

    try:
        success = user_service.reactivate_user(user_id)

        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return {"success": True, "message": f"User {user_id} reactivated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to reactivate user: {str(e)}"
        )
