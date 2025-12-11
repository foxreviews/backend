"""
Permissions globales pour FOX-Reviews.
Basées sur UserProfile.role (admin, manager, client).

4 RÔLES UNIQUEMENT (simples, efficaces, propres):

1️ ADMIN - Super user, accès total à toute l'application
2️ MANAGER - Admin limité, gestion contenu sans config sensible  
3️ CLIENT - Entreprise inscrite, accès uniquement à son tableau de bord
4️ VISITEUR - Pas de UserProfile (anonyme), accès public uniquement

UserProfile est la source de vérité (PAS User.is_staff).
"""
from rest_framework import permissions


class IsAuthenticated(permissions.BasePermission):
    """Utilisateur authentifié avec UserProfile valide.
    
    Exclut les VISITEURS (anonymes sans UserProfile).
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "profile")
        )


class IsAdmin(permissions.BasePermission):
    """Seuls les ADMIN peuvent accéder.
    
    ADMIN a accès total à toute l'application:
    - Gérer les utilisateurs
    - Gérer les entreprises
    - Gérer catégories / sous-catégories / villes
    - Forcer la rotation sponsorisée
    - Gérer les abonnements clients
    - Voir tous les logs / stats
    - Accéder à toutes les API internes (IA, import)
    - Supprimer ou désactiver des contenus
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False
        return request.user.profile.role == "admin"


class IsAdminOrManager(permissions.BasePermission):
    """ADMIN ou MANAGER peuvent accéder.
    
    MANAGER (admin limité) peut:
    - Gérer les entreprises (édition, validation, désactivation)
    - Gérer les avis décryptés
    - Gérer les sponsorisations (activation/désactivation uniquement)
    - Voir les stats (pas modifier réglages globaux)
    - Lancer régénération IA manuelle
    
    MANAGER ne peut PAS:
    - Gérer les rôles
    - Modifier la configuration système
    - Accéder aux logs techniques internes
    - Toucher au modèle automatique d'import
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False
        return request.user.profile.role in ["admin", "manager"]


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Lecture pour TOUS (même VISITEUR anonyme), écriture pour ADMIN uniquement.
    
    - GET, HEAD, OPTIONS: accessible à tous (même VISITEUR anonyme)
    - POST, PUT, PATCH, DELETE: ADMIN uniquement
    
    Utilisé pour:
    - Catégories (lecture publique, modification admin)
    - Sous-catégories (lecture publique, modification admin)
    - Villes (lecture publique, modification admin)
    """

    def has_permission(self, request, view):
        # Lecture pour TOUS (même anonymes/VISITEUR)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Écriture pour ADMIN uniquement
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False
        return request.user.profile.role == "admin"


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Propriétaire de l'objet (CLIENT) ou ADMIN.
    
    - ADMIN: accès total
    - CLIENT: uniquement son entreprise (via UserProfile.entreprise)
    - MANAGER: lecture uniquement
    - VISITEUR: pas d'accès
    
    CLIENT peut:
    - Voir son entreprise et son statut sponsorisé
    - Voir ses stats (clics, impressions, position rotation)
    - Mettre à jour ses informations publiques
    - Télécharger un avis de remplacement
    - Voir son statut de facturation et télécharger ses factures
    - Activer / résilier l'abonnement sponsorisé
    
    CLIENT ne peut PAS:
    - Modifier l'architecture ou les catégories
    - Voir les autres entreprises
    - Accéder aux données internes
    - Modifier la rotation
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, "profile")

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False

        profile = request.user.profile

        # ADMIN a tous les droits
        if profile.role == "admin":
            return True

        # MANAGER a lecture seule
        if profile.role == "manager":
            return request.method in permissions.SAFE_METHODS

        # CLIENT ne peut modifier que son entreprise
        if profile.role == "client":
            # Si l'objet a un attribut 'entreprise'
            if hasattr(obj, "entreprise") and profile.entreprise:
                return obj.entreprise == profile.entreprise
            # Si l'objet EST une entreprise
            if obj.__class__.__name__ == "Entreprise" and profile.entreprise:
                return obj == profile.entreprise

        return False


class CanManageSponsorship(permissions.BasePermission):
    """
    Gestion des sponsorisations selon les rôles.
    
    - ADMIN: peut tout gérer (CRUD complet + forcer rotation)
    - MANAGER: peut activer/désactiver uniquement (read + activate/deactivate)
    - CLIENT: peut voir ses propres sponsorisations et les activer/résilier
    - VISITEUR: pas d'accès
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False

        profile = request.user.profile

        # ADMIN peut tout faire
        if profile.role == "admin":
            return True

        # MANAGER peut lire et activer/désactiver
        if profile.role == "manager":
            # Autoriser lecture
            if request.method in permissions.SAFE_METHODS:
                return True
            # Autoriser PATCH pour activate/deactivate uniquement
            if request.method == "PATCH":
                return True
            return False

        # CLIENT doit avoir une entreprise pour créer sponsorisation
        if profile.role == "client" and request.method == "POST":
            return profile.entreprise is not None

        return profile.role in ["client", "admin"]

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request.user, "profile"):
            return False

        profile = request.user.profile

        # ADMIN a tous les droits
        if profile.role == "admin":
            return True

        # MANAGER peut uniquement activer/désactiver
        if profile.role == "manager":
            if request.method in permissions.SAFE_METHODS:
                return True
            # Uniquement PATCH pour changements de statut
            if request.method == "PATCH":
                return True
            return False

        # CLIENT ne peut gérer que les sponsorisations de son entreprise
        if profile.role == "client" and profile.entreprise:
            return obj.pro_localisation.entreprise == profile.entreprise

        return False


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Lecture pour TOUS (même VISITEUR anonyme), écriture pour authentifiés avec UserProfile.
    
    - GET, HEAD, OPTIONS: accessible à tous (même VISITEUR anonyme)
    - POST, PUT, PATCH, DELETE: Utilisateurs authentifiés avec UserProfile
    
    Utilisé pour:
    - Entreprises (lecture publique, modification authentifiée)
    - Avis (lecture publique, modification authentifiée)
    - ProLocalisation (lecture publique, modification authentifiée)
    """

    def has_permission(self, request, view):
        # Lecture pour TOUS (même anonymes/VISITEUR)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Écriture pour utilisateurs authentifiés avec UserProfile
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, "profile")


class IsPublicReadOnly(permissions.BasePermission):
    """
    Lecture seule pour TOUS (même VISITEUR anonyme).
    
    VISITEUR (anonyme, pas de UserProfile) peut:
    - Utiliser le moteur de recherche
    - Consulter les pages pros
    - Voir les avis décryptés
    - Voir les catégories et villes
    - Contacter un pro directement
    
    Aucune modification n'est autorisée.
    Utilisé pour les endpoints publics (search, entreprises, avis).
    """

    def has_permission(self, request, view):
        # Lecture seule pour TOUS (même anonymes)
        return request.method in permissions.SAFE_METHODS
