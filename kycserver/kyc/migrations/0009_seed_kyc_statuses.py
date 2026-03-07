from django.db import migrations

def seed_statuses(apps, schema_editor):
    KYCStatus = apps.get_model("kyc", "KYCStatus")

    statuses = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    for code, name in statuses:
        KYCStatus.objects.get_or_create(
            code=code,
            defaults={"name": name}
        )

class Migration(migrations.Migration):

    dependencies = [
        ("kyc", "0008_kycquestion_party_type_kycquestionevent_party_type_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_statuses, migrations.RunPython.noop),
    ]