"""
URLs for users auth endpoints.
"""

from django.urls import path

from foxreviews.users.api.auth import account_me
from foxreviews.users.api.auth import account_update
from foxreviews.users.api.auth import login
from foxreviews.users.api.auth import password_reset_request
from foxreviews.users.api.auth import register

app_name = "users_api"

urlpatterns = [
    # Auth
    path("register/", register, name="register"),
    path("login/", login, name="login"),
    path("password-reset/", password_reset_request, name="password-reset"),
    
    # Account
    path("me/", account_me, name="account-me"),
    path("update/", account_update, name="account-update"),
]
