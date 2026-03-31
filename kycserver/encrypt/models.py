from django.db import models
import pghistory

from base.models import BaseModel

# Create your models here.
@pghistory.track()
class EncryptionType(BaseModel):
    pass

@pghistory.track()
class EncryptionValue(BaseModel):
    ciphertext = models.BinaryField()
    nonce = models.BinaryField()  # 12 bytes for GCM
    tag = models.BinaryField()

    key_id = models.CharField(max_length=100)  # for rotation