from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = settings.AUTH_USER_MODEL


@receiver(post_save, sender=User)
def create_profile_on_user_creation(sender, instance, created, **kwargs):
    if created:
        # Always ensure a profile exists
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        # If a superuser is created, enforce ADMIN role on UserProfile
        if getattr(instance, "is_superuser", False):
            profile.role = UserProfile.Role.ADMIN
            profile.save(update_fields=["role"]) 
