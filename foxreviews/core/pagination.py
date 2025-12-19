from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class ResultsPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    page_query_param = "page"

    def get_results(self, data):
        return data

    def get_paginated_response(self, data):
        return Response(self.get_results(data))


class OptimizedCursorPagination(CursorPagination):
    """
    Pagination par curseur pour datasets massifs (> 500K enregistrements).

    Avantages vs OFFSET:
    - Performance constante O(1) même sur page 10,000
    - Résultats cohérents si données ajoutées pendant navigation
    - Pas de skip de lignes (OFFSET 100000 = scan 100K lignes)

    Inconvénients:
    - Pas de jump à page spécifique (page 50)
    - Navigation next/previous uniquement
    - Nécessite tri stable avec index composite (ordering, id)

    Usage:
        class VilleViewSet(CRUDViewSet):
            pagination_class = VilleCursorPagination  # Au lieu de ResultsPageNumberPagination
    """

    page_size = 20
    ordering = "-created_at"  # Doit avoir index composite (created_at, id)
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Retourne next/previous cursors au lieu de count total.

        Sur millions de données, COUNT(*) = 2-5s → évité.
        """
        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                # ❌ Pas de 'count' - trop coûteux sur millions
            }
        )


class VilleCursorPagination(OptimizedCursorPagination):
    """
    Pagination curseur pour Ville (millions d'enregistrements).

    Requires index: (nom, id) ou (created_at DESC, id DESC)
    """

    ordering = "nom"  # Index composite nécessaire
    page_size = 50


class CategorieCursorPagination(OptimizedCursorPagination):
    """Pagination curseur pour Categorie."""

    ordering = "ordre"
    page_size = 50


class SousCategorieCursorPagination(OptimizedCursorPagination):
    """Pagination curseur pour SousCategorie."""

    ordering = "ordre"
    page_size = 50


class EnterpriseCursorPagination(OptimizedCursorPagination):
    """Pagination curseur pour Enterprise (millions d'enregistrements)."""

    ordering = "-created_at"
    page_size = 20

