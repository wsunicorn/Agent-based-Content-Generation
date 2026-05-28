from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_job_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentrun",
            name="provider",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="job",
            name="llm_usage_by_provider",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
