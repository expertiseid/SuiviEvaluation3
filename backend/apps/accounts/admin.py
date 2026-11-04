from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, User

admin.site.site_header = "Administration — Expertise-ID Monitora"
admin.site.site_title = "Expertise-ID Monitora"
admin.site.index_title = "Administration"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Informations complémentaires", {"fields": ("role", "telephone", "zones_affectees")}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("libelle", "code", "visibilite_globale", "systeme")
