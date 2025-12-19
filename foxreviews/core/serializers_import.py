"""
Serializers pour les imports de données.
"""

from rest_framework import serializers

from foxreviews.core.models_import import ImportLog


class ImportLogSerializer(serializers.ModelSerializer):
    """Serializer pour ImportLog."""

    success_rate = serializers.ReadOnlyField()
    duration = serializers.ReadOnlyField()
    import_type_display = serializers.CharField(source="get_import_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ImportLog
        fields = [
            "id",
            "import_type",
            "import_type_display",
            "status",
            "status_display",
            "file_name",
            "file",
            "uploaded_by",
            "generate_ai_content",
            "ai_generation_started",
            "ai_generation_completed",
            "total_rows",
            "success_rows",
            "error_rows",
            "errors",
            "success_rate",
            "created_at",
            "started_at",
            "completed_at",
            "duration",
        ]
        read_only_fields = [
            "id",
            "status",
            "uploaded_by",
            "ai_generation_started",
            "ai_generation_completed",
            "total_rows",
            "success_rows",
            "error_rows",
            "errors",
            "created_at",
            "started_at",
            "completed_at",
        ]


class ImportUploadSerializer(serializers.Serializer):
    """Serializer pour l'upload d'un fichier d'import."""

    import_type = serializers.ChoiceField(
        choices=ImportLog.ImportType.choices,
        help_text="Type d'import à effectuer",
    )
    file = serializers.FileField(
        help_text="Fichier CSV ou Excel à importer",
    )
    generate_ai_content = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Générer automatiquement le contenu IA après l'import",
    )

    def validate_file(self, value):
        """Valide le fichier uploadé."""
        # Vérifie l'extension
        file_name = value.name.lower()
        allowed_extensions = [".csv", ".xlsx", ".xls"]

        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                f"Format de fichier non supporté. Formats acceptés: {', '.join(allowed_extensions)}",
            )

        # Vérifie la taille (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Fichier trop volumineux. Taille max: {max_size / 1024 / 1024}MB",
            )

        return value
