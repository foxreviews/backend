"""
Hooks de préprocessing et postprocessing pour drf-spectacular.
Ces hooks ajustent automatiquement la configuration de sécurité dans le schéma OpenAPI
en fonction des permissions réelles définies dans les vues.
"""

from rest_framework.permissions import AllowAny


def preprocess_exclude_security_for_public_endpoints(endpoints):
    """
    Hook de preprocessing pour identifier les endpoints publics (AllowAny).
    Marque ces endpoints pour qu'ils n'aient pas de sécurité dans le schéma généré.
    """
    for path, path_regex, method, callback in endpoints:
        # Récupérer les permissions de la vue
        view = callback.cls if hasattr(callback, 'cls') else callback
        
        # Déterminer les permissions pour cette action
        if hasattr(view, 'get_permissions'):
            # Pour les ViewSets avec get_permissions dynamiques
            try:
                # Créer une instance temporaire pour tester
                view_instance = view()
                view_instance.action = method.lower()
                view_instance.request = None
                permissions = view_instance.get_permissions()
            except Exception:
                # Si on ne peut pas instancier, utiliser permission_classes
                permissions = getattr(view, 'permission_classes', [])
        else:
            permissions = getattr(view, 'permission_classes', [])
        
        # Vérifier si AllowAny est dans les permissions
        is_public = any(isinstance(perm, AllowAny) or perm == AllowAny for perm in permissions)
        
        # Marquer l'endpoint comme public si nécessaire
        if is_public:
            if not hasattr(callback, '_spectacular_annotation'):
                callback._spectacular_annotation = {}
            callback._spectacular_annotation['exclude_security'] = True
    
    return endpoints


def postprocess_schema_security(result, generator, request, public):
    """
    Hook de postprocessing pour nettoyer la configuration de sécurité dans le schéma.
    Supprime la sécurité des endpoints publics et simplifie la structure.
    """
    if 'paths' not in result:
        return result
    
    # Liste des endpoints qui doivent être publics (AllowAny)
    public_endpoints = [
        # Auth publics
        ('post', '/api/auth/login/'),
        ('post', '/api/auth/register/'),
        ('post', '/api/auth/password/reset/'),
        ('post', '/api/auth/password/reset/confirm/'),
        ('post', '/api/auth/token/refresh/'),
        ('post', '/api/auth/token/verify/'),
        
        # Tours publics (lecture seulement)
        ('get', '/api/tours/'),
        ('get', '/api/tours/{slug}/'),
        ('get', '/api/tours/search_available/'),
        ('get', '/api/tours/{slug}/available_schedules/'),
        ('get', '/api/tours/featured/'),
        
        # Blog publics (lecture seulement)
        ('get', '/api/blog/'),
        ('get', '/api/blog/{slug}/'),
        ('get', '/api/blog/categories/'),
        
        # Pages publiques (lecture seulement)
        ('get', '/api/pages/'),
        ('get', '/api/pages/{slug}/'),
        
        # FAQs publiques (lecture seulement)
        ('get', '/api/faqs/'),
        ('get', '/api/faqs/{id}/'),
        ('get', '/api/faqs/categories/'),
        
        # Testimonials publics (lecture seulement)
        ('get', '/api/testimonials/'),
        ('get', '/api/testimonials/{id}/'),
        
        # Chatbot public (accessible aux anonymes)
        ('get', '/api/intelligent/conversations/'),
        ('post', '/api/intelligent/conversations/'),
        ('get', '/api/intelligent/conversations/{id}/'),
        ('put', '/api/intelligent/conversations/{id}/'),
        ('patch', '/api/intelligent/conversations/{id}/'),
        ('delete', '/api/intelligent/conversations/{id}/'),
        ('post', '/api/intelligent/conversations/send_message/'),
        
        # Schéma OpenAPI public
        ('get', '/api/schema/'),
    ]
    
    # Parcourir tous les paths du schéma
    for path, path_item in result['paths'].items():
        for method, operation in path_item.items():
            if method.lower() in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                # Vérifier si cet endpoint est public
                is_public_endpoint = any(
                    method.lower() == pub_method and path == pub_path 
                    for pub_method, pub_path in public_endpoints
                )
                
                # Si c'est un endpoint public, supprimer la sécurité
                if is_public_endpoint:
                    operation['security'] = []
                else:
                    # Pour les endpoints protégés, utiliser bearerAuth uniquement
                    operation['security'] = [{"bearerAuth": []}]
    
    # Nettoyer les schémas de sécurité inutilisés
    if 'components' in result and 'securitySchemes' in result['components']:
        # Garder seulement bearerAuth
        result['components']['securitySchemes'] = {
            'bearerAuth': result['components']['securitySchemes'].get('bearerAuth', {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'JWT token obtenu via `/api/auth/login/`',
            })
        }
    
    return result
