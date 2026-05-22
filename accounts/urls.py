from django.urls import path
from .views import (
    signup, login_view, forgot_password, logout_view,
    reset_password_api, delete_account,
    verify_email, resend_verification_email, me,
    update_profile, change_password, update_email,
)

urlpatterns = [
    path("signup/", signup),
    path("login/", login_view),
    path("forgot-password/", forgot_password),
    path("logout/", logout_view, name="logout"),
    path("reset-password/", reset_password_api),
    path("delete-account/", delete_account, name="delete-account"),
    path("verify-email/<str:uidb64>/<str:token>/", verify_email, name="verify-email"),
    path("resend-verification/", resend_verification_email, name="resend-verification"),
    path("me/", me, name="me"),
    # Profile settings
    path("update-profile/", update_profile, name="update-profile"),
    path("change-password/", change_password, name="change-password"),
    path("update-email/", update_email, name="update-email"),
]
