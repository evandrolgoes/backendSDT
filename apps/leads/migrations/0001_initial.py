from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nome", models.CharField(max_length=150)),
                ("whatsapp", models.CharField(max_length=30)),
                ("email", models.EmailField(max_length=254)),
                ("perfil", models.CharField(max_length=80)),
                ("trabalho_ocupacao_atual", models.CharField(max_length=150)),
                ("empresa_atual", models.CharField(max_length=150)),
                ("landing_page", models.CharField(max_length=150)),
                ("data", models.DateTimeField(auto_now_add=True)),
                ("objetivo", models.CharField(max_length=200)),
                ("mensagem", models.TextField(blank=True)),
            ],
            options={"ordering": ["-data", "-created_at"]},
        ),
    ]
