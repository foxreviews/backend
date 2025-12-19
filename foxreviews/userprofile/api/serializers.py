from rest_framework import serializers

from ..models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer complet pour UserProfile avec tous les champs."""

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="role", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "role",
            # Contact
            "phone",
            "emergency_contact_name",
            "emergency_contact_phone",
            # Identity & Documents
            "date_of_birth",
            "nationality",
            "passport_number",
            # Address
            "address_line1",
            "address_line2",
            "city",
            "postal_code",
            "country",
            # Health & Preferences
            "dietary_restrictions",
            "medical_conditions",
            "preferences",
            # UI Settings
            "avatar_url",
            "timezone",
            "language",
            "currency",
            # Metadata
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "role",
            "created_at",
            "updated_at",
        ]
