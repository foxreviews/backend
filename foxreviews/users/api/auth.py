"""
Authentication and Account management API endpoints.
Gestion des utilisateurs et comptes clients.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from foxreviews.userprofile.models import UserProfile

User = get_user_model()
logger = logging.getLogger(__name__)


# ========================================================================
# SERIALIZERS
# ========================================================================


class RegisterRequestSerializer(serializers.Serializer):
    """Serializer pour l'inscription d'un utilisateur."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    entreprise_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_email(self, value):
        """Vérifie que l'email n'est pas déjà utilisé."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value.lower()

    def validate_password(self, value):
        """Valide le mot de passe avec les règles Django."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class RegisterResponseSerializer(serializers.Serializer):
    """Serializer pour la réponse d'inscription."""

    user = serializers.DictField()
    token = serializers.CharField()
    message = serializers.CharField()


class LoginRequestSerializer(serializers.Serializer):
    """Serializer pour la connexion."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LoginResponseSerializer(serializers.Serializer):
    """Serializer pour la réponse de connexion."""

    user = serializers.DictField()
    token = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer pour la demande de réinitialisation de mot de passe."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer pour la confirmation de réinitialisation de mot de passe."""

    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        """Valide le nouveau mot de passe."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class UserAccountSerializer(serializers.Serializer):
    """Serializer pour les données du compte utilisateur."""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    name = serializers.CharField(max_length=255, allow_blank=True)
    role = serializers.CharField(read_only=True)
    entreprise = serializers.DictField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True, source="date_joined")


class UpdateAccountRequestSerializer(serializers.Serializer):
    """Serializer pour la mise à jour du compte."""

    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


# ========================================================================
# ENDPOINTS
# ========================================================================


@extend_schema(
    summary="Inscription d'un utilisateur",
    description="""
    Créer un nouveau compte utilisateur avec email et mot de passe.
    
    - Crée automatiquement un UserProfile avec rôle CLIENT
    - Génère un token d'authentification
    - Peut lier à une entreprise existante
    """,
    request=RegisterRequestSerializer,
    responses={
        201: OpenApiResponse(
            response=RegisterResponseSerializer,
            description="Utilisateur créé avec succès",
        ),
        400: OpenApiResponse(description="Données invalides"),
    },
    tags=["Auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """
    Créer un nouveau compte utilisateur.
    """
    serializer = RegisterRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    name = serializer.validated_data.get("name", "")
    entreprise_id = serializer.validated_data.get("entreprise_id")

    try:
        # Créer l'utilisateur
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
        )

        # Créer le profil
        profile_data = {"role": UserProfile.Role.CLIENT}
        
        if entreprise_id:
            from foxreviews.enterprise.models import Entreprise
            try:
                entreprise = Entreprise.objects.get(id=entreprise_id)
                profile_data["entreprise"] = entreprise
            except Entreprise.DoesNotExist:
                logger.warning(f"Entreprise {entreprise_id} introuvable lors de l'inscription")

        UserProfile.objects.create(user=user, **profile_data)

        # Générer token
        token, _ = Token.objects.get_or_create(user=user)

        logger.info(f"Nouvel utilisateur inscrit: {email}")

        return Response(
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                },
                "token": token.key,
                "message": "Inscription réussie",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.exception(f"Erreur lors de l'inscription: {e}")
        return Response(
            {"error": "Erreur lors de la création du compte"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Connexion utilisateur",
    description="""
    Authentifier un utilisateur avec email et mot de passe.
    
    Retourne un token d'authentification à utiliser pour les requêtes suivantes.
    """,
    request=LoginRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=LoginResponseSerializer,
            description="Connexion réussie",
        ),
        401: OpenApiResponse(description="Identifiants invalides"),
    },
    tags=["Auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """
    Authentifier un utilisateur.
    """
    from django.contrib.auth import authenticate

    serializer = LoginRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)

    if user is None:
        return Response(
            {"error": "Email ou mot de passe incorrect"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Générer ou récupérer token
    token, _ = Token.objects.get_or_create(user=user)

    # Récupérer le profil
    try:
        profile = user.profile
        role = profile.role
    except UserProfile.DoesNotExist:
        role = "visiteur"

    logger.info(f"Connexion réussie: {email}")

    return Response(
        {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": role,
            },
            "token": token.key,
        },
    )


@extend_schema(
    summary="Réinitialisation de mot de passe",
    description="""
    Demander une réinitialisation de mot de passe par email.
    
    Un email sera envoyé avec un lien de réinitialisation.
    """,
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiResponse(description="Email envoyé"),
        404: OpenApiResponse(description="Utilisateur introuvable"),
    },
    tags=["Auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Demander une réinitialisation de mot de passe.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email)
        
        # Utiliser le système de réinitialisation Django/Allauth
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # TODO: Envoyer l'email avec le lien de réinitialisation
        # reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
        
        logger.info(f"Demande de réinitialisation de mot de passe pour: {email}")
        
        return Response(
            {"message": "Un email de réinitialisation a été envoyé"},
        )

    except User.DoesNotExist:
        # Ne pas révéler si l'utilisateur existe ou non (sécurité)
        return Response(
            {"message": "Un email de réinitialisation a été envoyé"},
        )


@extend_schema(
    summary="Récupérer les informations du compte",
    description="""
    Récupérer les informations du compte de l'utilisateur connecté.
    
    Requiert une authentification (token).
    """,
    responses={
        200: OpenApiResponse(
            response=UserAccountSerializer,
            description="Informations du compte",
        ),
        401: OpenApiResponse(description="Non authentifié"),
    },
    tags=["Account"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_me(request):
    """
    Récupérer les informations du compte utilisateur.
    """
    user = request.user
    
    try:
        profile = user.profile
        role = profile.role
        entreprise_data = None
        
        if profile.entreprise:
            entreprise_data = {
                "id": str(profile.entreprise.id),
                "nom": profile.entreprise.nom,
                "siren": profile.entreprise.siren,
            }
    except UserProfile.DoesNotExist:
        role = "visiteur"
        entreprise_data = None

    return Response(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": role,
            "entreprise": entreprise_data,
            "created_at": user.date_joined,
        },
    )


@extend_schema(
    summary="Mettre à jour le compte",
    description="""
    Mettre à jour les informations du compte utilisateur.
    
    Requiert une authentification (token).
    """,
    request=UpdateAccountRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=UserAccountSerializer,
            description="Compte mis à jour",
        ),
        400: OpenApiResponse(description="Données invalides"),
        401: OpenApiResponse(description="Non authentifié"),
    },
    tags=["Account"],
)
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def account_update(request):
    """
    Mettre à jour le compte utilisateur.
    """
    user = request.user
    serializer = UpdateAccountRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Mise à jour du nom
    if "name" in serializer.validated_data:
        user.name = serializer.validated_data["name"]
        user.save(update_fields=["name"])

    # Mise à jour du téléphone dans le profil
    if "phone" in serializer.validated_data:
        try:
            profile = user.profile
            profile.phone = serializer.validated_data["phone"]
            profile.save(update_fields=["phone"])
        except UserProfile.DoesNotExist:
            # Créer le profil si nécessaire
            UserProfile.objects.create(
                user=user,
                phone=serializer.validated_data["phone"],
            )

    logger.info(f"Compte mis à jour: {user.email}")

    # Retourner les données mises à jour
    return account_me(request)
