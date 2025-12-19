"""
ViewSets pour les imports de données.
"""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from foxreviews.core.import_service import ImportService
from foxreviews.core.models_import import ImportLog
from foxreviews.core.serializers_import import ImportLogSerializer, ImportUploadSerializer


class ImportViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les imports de données.

    Liste tous les imports et permet d'uploader de nouveaux fichiers.
    """

    queryset = ImportLog.objects.all()
    serializer_class = ImportLogSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["import_type", "status"]
    search_fields = ["file_name"]
    ordering_fields = ["created_at", "completed_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        """Associe l'utilisateur actuel à l'import."""
        serializer.save(uploaded_by=self.request.user)

    @action(detail=False, methods=["post"])
    def upload(self, request):
        """
        Upload un fichier et démarre l'import.

        Format attendu:
        - import_type: ENTREPRISE | VILLE | CATEGORIE | SOUS_CATEGORIE
        - file: fichier CSV ou Excel

        Formats CSV attendus:

        **Entreprises:**
        ```
        siren,siret,nom,nom_commercial,adresse,code_postal,ville_nom,naf_code,naf_libelle,telephone,email_contact,site_web,is_active
        123456789,12345678900001,Ma Société,Mon Enseigne,1 rue Example,75001,Paris,62.01Z,Programmation informatique,0123456789,contact@example.com,https://example.com,true
        ```

        **Catégories:**
        ```
        nom,description,meta_description,ordre
        Artisans,Catégorie des artisans,Trouvez les meilleurs artisans,1
        ```

        **Sous-catégories:**
        ```
        nom,categorie,description,meta_description,mots_cles,ordre
        Plombier,Artisans,Plombiers professionnels,Trouvez un plombier,plomberie sanitaire,1
        ```
        """
        upload_serializer = ImportUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        # Crée l'ImportLog
        import_log = ImportLog.objects.create(
            import_type=upload_serializer.validated_data["import_type"],
            file=upload_serializer.validated_data["file"],
            file_name=upload_serializer.validated_data["file"].name,
            uploaded_by=request.user,
            generate_ai_content=upload_serializer.validated_data.get("generate_ai_content", False),
            status=ImportLog.ImportStatus.PENDING,
        )

        # Option 1: Traitement asynchrone (recommandé pour production)
        # Décommentez pour activer Celery
        # from foxreviews.core.tasks_ai import process_import_file_async
        # process_import_file_async.delay(import_log.id)
        # return Response(
        #     {
        #         "id": import_log.id,
        #         "message": "Import en cours de traitement. Vérifiez le statut dans quelques minutes.",
        #         "status": import_log.status,
        #     },
        #     status=status.HTTP_202_ACCEPTED,
        # )

        # Option 2: Traitement synchrone (développement uniquement)
        # ⚠️ Peut bloquer l'API pour les gros fichiers (>5000 lignes)
        import_service = ImportService(import_log)
        import_service.process_file()

        # Recharge l'objet depuis la base de données
        import_log.refresh_from_db()

        serializer = self.get_serializer(import_log)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """
        Relance un import qui a échoué.
        """
        import_log = self.get_object()

        # Vérifie que l'import peut être relancé
        if import_log.status not in [
            ImportLog.ImportStatus.ERROR,
            ImportLog.ImportStatus.PARTIAL,
        ]:
            return Response(
                {"detail": "Seuls les imports en erreur ou partiels peuvent être relancés."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Réinitialise les compteurs
        import_log.status = ImportLog.ImportStatus.PENDING
        import_log.started_at = None
        import_log.completed_at = None
        import_log.total_rows = 0
        import_log.success_rows = 0
        import_log.error_rows = 0
        import_log.errors = []
        import_log.save()

        # Relance l'import
        import_service = ImportService(import_log)
        import_service.process_file()

        import_log.refresh_from_db()
        serializer = self.get_serializer(import_log)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Retourne des statistiques sur les imports.
        """
        from django.db.models import Avg, Count, Sum

        stats = {
            "total_imports": ImportLog.objects.count(),
            "by_status": dict(
                ImportLog.objects.values("status").annotate(count=Count("id")).values_list("status", "count"),
            ),
            "by_type": dict(
                ImportLog.objects.values("import_type")
                .annotate(count=Count("id"))
                .values_list("import_type", "count"),
            ),
            "total_rows_processed": ImportLog.objects.aggregate(total=Sum("total_rows"))["total"] or 0,
            "total_success_rows": ImportLog.objects.aggregate(total=Sum("success_rows"))["total"] or 0,
            "total_error_rows": ImportLog.objects.aggregate(total=Sum("error_rows"))["total"] or 0,
            "average_success_rate": ImportLog.objects.filter(total_rows__gt=0).aggregate(
                avg=(Sum("success_rows") * 100.0 / Sum("total_rows")),
            )["avg"]
            or 0,
        }

        return Response(stats)

    @action(detail=True, methods=["post"])
    def generate_ai(self, request, pk=None):
        """
        Déclenche la génération de contenu IA pour un import.

        POST /api/imports/{id}/generate_ai/

        Cette action lance une tâche Celery en arrière-plan pour générer
        le contenu IA (avis, descriptions) pour les entités importées.

        Conditions:
        - L'import doit être terminé (SUCCESS ou PARTIAL)
        - Le type d'import doit être ENTREPRISE, CATEGORIE ou SOUS_CATEGORIE

        Returns:
            - 200: Génération lancée avec succès
            - 400: Import non éligible (mauvais statut ou type)
        """
        import_log = self.get_object()

        # Vérifications
        if import_log.status not in [ImportLog.ImportStatus.SUCCESS, ImportLog.ImportStatus.PARTIAL]:
            return Response(
                {"error": "L'import doit être terminé avec succès pour générer du contenu IA."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if import_log.import_type not in [
            ImportLog.ImportType.ENTREPRISE,
            ImportLog.ImportType.SOUS_CATEGORIE,
            ImportLog.ImportType.CATEGORIE,
        ]:
            return Response(
                {"error": f"La génération IA n'est pas disponible pour le type {import_log.get_import_type_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Active la génération IA
        if not import_log.generate_ai_content:
            import_log.generate_ai_content = True
            import_log.save(update_fields=["generate_ai_content"])

        # Lance la tâche Celery
        from foxreviews.core.tasks_ai import generate_ai_content_for_import

        generate_ai_content_for_import.delay(import_log.id)

        return Response(
            {
                "message": "Génération IA lancée en arrière-plan. Vérifiez le statut dans quelques minutes.",
                "import_id": import_log.id,
                "ai_generation_started": import_log.ai_generation_started,
                "ai_generation_completed": import_log.ai_generation_completed,
            },
        )
