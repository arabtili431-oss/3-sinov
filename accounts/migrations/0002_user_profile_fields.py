"""Foydalanuvchiga rasm, bio va bloklash maydonlarini qo'shadi."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True, upload_to="avatars/", verbose_name="Rasm"),
        ),
        migrations.AddField(
            model_name="user",
            name="bio",
            field=models.TextField(blank=True, verbose_name="Qisqacha ma'lumot"),
        ),
        migrations.AddField(
            model_name="user",
            name="is_blocked",
            field=models.BooleanField(default=False, verbose_name="Bloklangan"),
        ),
        migrations.AddField(
            model_name="user",
            name="blocked_reason",
            field=models.CharField(blank=True, max_length=200, verbose_name="Bloklash sababi"),
        ),
        migrations.AddField(
            model_name="user",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Oxirgi faollik"),
        ),
    ]
