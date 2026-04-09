from django.db import models

class AnswerTypeEnum(models.TextChoices):
        NUMBER = "N", "number"
        TEXT   = "T", "text"
        BOOL   = "B", "bool"
        SINGLE = "S", "single"
        MULTI  = "M", "multi"
        DATE   = "D", "date"
        RANGE  = "R", "date_range"
        PHONE  = "P", "phone_number"
        EMAIL  = "E", "email_address"