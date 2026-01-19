from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

from kycserver.base.models import BaseModel

# Create your models here.
# Users

class UserRole(models.TextChoices):
    ADMIN = 'A', 'Admin'
    MANAGER = 'M', 'Manager'
    STAFF = 'S', 'Office Staff'
    GUEST = 'G', 'Guest'
    PROBATION = 'P', "Probation Employee"
    CONTRACTOR = 'C', "Contractor"

class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Users must have a username")
        role = extra_fields.get("role", UserRole.GUEST)
        if role not in UserRole.values:
            raise ValueError(f"Invalid role: {role}")
        extra_fields["role"] = role
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not extra_fields.get('is_staff'):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get('is_superuser'):
            raise ValueError("Superuser must have is_superuser=True.")
        
        extra_fields.setdefault('role', UserRole.ADMIN)
        return self.create_user(username, password, **extra_fields)
    
class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=1, choices=UserRole.choices, default=UserRole.GUEST)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []  # no other required fields for createsuperuser

    def __str__(self):
        return self.username
    
class FieldPermissions(models.Model):
    role = models.CharField(max_length=1, choices=UserRole.choices, default=UserRole.GUEST)
    model_name = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255)
    permission = models.PositiveIntegerField(default=0)

    class Flag:
        VIEW = 1 << 0
        EDIT = 1 << 1
        ADD = 1 << 2
        DELETE = 1 << 3

    def has_flag(self, flag):
        return bool(self.permission & flag)

    def add_flag(self, flag):
        self.permission |= flag
        self.save(update_fields=["permission"])

    def remove_flag(self, flag):
        self.permission &= ~flag
        self.save(update_fields=["permission"])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'model_name', 'field_name'],
                name='unique_role_model_field'
            ),
        ]
