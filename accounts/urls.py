from django.urls import path
from .views import signup, login_view, forgot_password,logout_view,reset_password_api,delete_account

urlpatterns = [
    path("signup/", signup),
    path("login/", login_view),
    path("forgot-password/", forgot_password),
    path("logout/", logout_view, name="logout"),
    path("reset-password/", reset_password_api),
    path("delete-account/", delete_account, name="delete-account"),

]
