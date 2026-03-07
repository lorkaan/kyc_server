from django.db import migrations

def create_party_types(apps, schema_editor):
    PartyType = apps.get_model("party", "PartyType")

    defaults = [
        ("person", "Person", "An individual human being"),
        ("company", "Company", "A registered company")
    ]

    for code, name, description in defaults:
        PartyType.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description
            }
        )

def remove_party_types(apps, schema_editor):
    PartyType = apps.get_model("party", "PartyType")
    PartyType.objects.filter(
        code__in=[
            "person",
            "company"
        ]
    ).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("party", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_party_types, remove_party_types),
    ]