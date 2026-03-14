from django.contrib import admin

from .models import Attachment, AuditLog

admin.site.register(AuditLog)
admin.site.register(Attachment)
