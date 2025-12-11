from django.contrib import admin

from .models import UserProfile


class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "nationality",
        "country",
        "city",
        "created_at",
        "updated_at",
    )
    list_filter = ("country", "nationality", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "passport_number",
        "city",
        "emergency_contact_name",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


admin.site.register(UserProfile, UserProfileAdmin)
