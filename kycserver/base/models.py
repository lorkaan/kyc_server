from django.db import models
import uuid

# Create your models here.

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class GenericTargetMixin(models.Model):
    object_type = models.CharField(max_length=100)
    object_id = models.UUIDField()

    class Meta:
        abstract = True

    def set_target(self, obj):
        self.object_type = obj.__class__.__name__
        self.object_id = obj.pk

    def get_target_model(self):
        from django.apps import apps
        return apps.get_model(self.object_type)

    def get_target(self):
        model = self.get_target_model()
        return model.objects.get(pk=self.object_id)