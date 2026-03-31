from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="language",
            field=models.CharField(
                blank=True,
                default="English",
                help_text="Output language (e.g. English, Vietnamese, French, Spanish)",
                max_length=50,
            ),
        ),
    ]
