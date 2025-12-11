from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import models

FERNET_KEY = getattr(settings, "FERNET_SECRET_KEY", None)
fernet = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None


class EncryptedCharField(models.CharField):
    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return None

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return fernet.encrypt(value.encode()).decode()

    def to_python(self, value):
        if value is None or value == "":
            return value
        try:
            # Already decrypted
            return (
                value
                if not value.startswith("gAAAA")
                else fernet.decrypt(value.encode()).decode()
            )
        except InvalidToken:
            return None
