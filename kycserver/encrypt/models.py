from django.db import models

from kyc.data_types import AnswerTypeEnum
import pghistory
from .handlers import CipherPol

from base.models import BaseModel
from django.core.exceptions import ValidationError

REPRESENTATION_HANDLERS = {
    AnswerTypeEnum.NUMBER: "value_number",
    AnswerTypeEnum.TEXT: "value_text",
    AnswerTypeEnum.BOOL: "value_bool",
    AnswerTypeEnum.DATE: "value_date",
    AnswerTypeEnum.PHONE: "value_phone",
    AnswerTypeEnum.EMAIL: "value_email",
}

# Create your models here.
def get_algorithm_choices():
    return [(key, key) for key in CipherPol.REGISTRY.keys()]

def get_allowed_data_type_choices():
    return [
        (k, v) for k, v in AnswerTypeEnum.choices
        if k in REPRESENTATION_HANDLERS.keys()
    ]

@pghistory.track()
class EncryptionType(BaseModel):

    class Status(models.TextChoices):
        SAFE = "S", "Safe"           # Recommended for new data
        DEPRECATED = "D", "Deprecated"  # Still decryptable but should not be used for new data
        UNSAFE = "U", "Unsafe"       # Known weaknesses; should not be used at all
        EXPERIMENTAL = "E", "Experimental"  # Newly added, not yet vetted for production


    algorithm = models.CharField(max_length=50, choices=get_algorithm_choices(), default="AES256_GCM")
    status = models.CharField(max_length=1, choices=Status, default=Status.EXPERIMENTAL)

    def clean(self):
        if self.algorithm not in CipherPol.REGISTRY:
            raise ValidationError("Invalid encryption algorithm")
        
    

@pghistory.track()
class EncryptionValue(BaseModel):
    encrypt_type = models.ForeignKey(EncryptionType, on_delete=models.CASCADE, null=True)
    ciphertext = models.TextField()
    data_type = models.CharField(max_length=1, choices=get_allowed_data_type_choices(), default=AnswerTypeEnum.TEXT)
    dek = models.TextField()
    key_id = models.CharField(max_length=100, blank=True, null=True)

    def clean(self):
        super().clean()

        # Ensure data_type is in the allowed whitelist
        allowed_types = {k for k, _ in get_allowed_data_type_choices()}
        if self.data_type not in allowed_types:
            raise ValidationError(
                {"data_type": f"Data type '{self.data_type}' is not allowed for encryption."}
            )
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)