from django.db import migrations, models


def migrate_legacy_content(apps, schema_editor):
    MarketNewsPost = apps.get_model("mercado", "MarketNewsPost")

    for post in MarketNewsPost.objects.all():
        blocks = []

        texto_completo = getattr(post, "texto_completo", "") or ""
        if texto_completo.strip():
            blocks.append({"type": "text", "content": texto_completo.strip(), "caption": ""})

        html_embed = getattr(post, "html_embed", "") or ""
        if html_embed.strip():
            blocks.append({"type": "html", "content": html_embed.strip(), "caption": ""})

        post.resumo = (texto_completo.strip()[:280] if texto_completo.strip() else "")
        post.conteudo = blocks
        post.save(update_fields=["resumo", "conteudo"])


class Migration(migrations.Migration):

    dependencies = [
        ("mercado", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketnewspost",
            name="conteudo",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="marketnewspost",
            name="resumo",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(migrate_legacy_content, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="audio",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="categoria",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="html_embed",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="imagem_capa",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="texto_completo",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="video_url",
        ),
    ]
