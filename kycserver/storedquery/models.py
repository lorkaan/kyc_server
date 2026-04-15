from django.db import models
from django.db.models import Q
from django.apps import apps

from base.models import BaseModel
from users.models import User

# Create your models here.
class SavedQuery(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    model = models.CharField(
        max_length=100,
        help_text="app_label.ModelName"
    )

    query = models.JSONField()

    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="owned_queries"
    )

    is_system = models.BooleanField(
        default=False,
        help_text="System-managed default query"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(is_system=True, owner__isnull=True) |
                    Q(is_system=False)
                ),
                name="system_queries_have_no_owner"
            )
        ]

    def to_ast_payload(self):
        return {
            "query": self.query,
            "model": self.model
        }
    
    def get_model_class(self):
        app_label, model_name = self.model.split(".")
        return apps.get_model(app_label, model_name)

# I need to change the choices I think and check the target_type and target_id, 
# I dont know why I cant just use the Permissions
class SavedQueryPermission(models.Model):
    class TargetType(models.TextChoices):
        USER = "user", "User"
        ROLE = "role", "Role"
        ALL = "all", "All users"
        # future: TEAM, COMPANY, ORG

    class Level(models.IntegerChoices):
        VIEW = 1
        EDIT = 2

    query = models.ForeignKey(
        SavedQuery,
        on_delete=models.CASCADE,
        related_name="permissions"
    )

    target_type = models.CharField(
        max_length=10,
        choices=TargetType.choices
    )

    target_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID, role code, etc."
    )

    level = models.PositiveSmallIntegerField(
        choices=Level.choices,
        default=Level.VIEW
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["query", "target_type", "target_id"],
                name="unique_query_permission"
            )
        ]