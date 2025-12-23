"""URLs for users auth endpoints."""

from django.urls import re_path

from foxreviews.users.api.auth import account_me
from foxreviews.users.api.auth import account_update
from foxreviews.users.api.auth import login
from foxreviews.users.api.auth import password_reset_request
from foxreviews.users.api.auth import register

app_name = "users_api"

urlpatterns = [
    # Auth
    re_path(r"^register/?$", register, name="register"),
    re_path(r"^login/?$", login, name="login"),
    re_path(r"^password-reset/?$", password_reset_request, name="password-reset"),
    
    # Account
    re_path(r"^me/?$", account_me, name="account-me"),
    re_path(r"^update/?$", account_update, name="account-update"),
]
