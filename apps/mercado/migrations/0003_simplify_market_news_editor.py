from html import escape

from django.db import migrations, models


def _text_to_html(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if "<" in text and ">" in text:
        return text
    paragraphs = [item.strip() for item in text.split("\n\n") if item.strip()]
    return "".join(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def _blocks_to_html(blocks):
    parts = []
    for block in blocks or []:
        block_type = str((block or {}).get("type") or "text").strip().lower()
        content = str((block or {}).get("content") or "").strip()
        caption = str((block or {}).get("caption") or "").strip()
        if not content:
            continue

        if block_type == "image":
            figure = f'<figure><img src="{escape(content, quote=True)}" alt="{escape(caption or "Imagem", quote=True)}" />'
            if caption:
                figure += f"<figcaption>{escape(caption)}</figcaption>"
            figure += "</figure>"
            parts.append(figure)
            continue

        if block_type == "video":
            source = escape(content, quote=True)
            if content.lower().endswith((".mp4", ".webm", ".ogg")):
                media = f'<video controls src="{source}"></video>'
            else:
                media = f'<iframe src="{source}" allowfullscreen></iframe>'
            if caption:
                media += f"<p>{escape(caption)}</p>"
            parts.append(media)
            continue

        if block_type == "html":
            parts.append(content)
            continue

        parts.append(_text_to_html(content))

    return "\n".join(part for part in parts if part)


def migrate_to_html(apps, schema_editor):
    MarketNewsPost = apps.get_model("mercado", "MarketNewsPost")

    for post in MarketNewsPost.objects.all():
        html = _blocks_to_html(getattr(post, "conteudo", None))
        if not html:
            html = _text_to_html(getattr(post, "resumo", ""))
        post.conteudo_html = html
        post.save(update_fields=["conteudo_html"])


class Migration(migrations.Migration):

    dependencies = [
        ("mercado", "0002_rework_marketnewspost_blog_format"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketnewspost",
            name="conteudo_html",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(migrate_to_html, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="conteudo",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="resumo",
        ),
        migrations.RemoveField(
            model_name="marketnewspost",
            name="tags",
        ),
    ]
