from django.contrib import admin

from .models import Indicateur, ValeurIndicateur


class ValeurIndicateurInline(admin.TabularInline):
    model = ValeurIndicateur
    extra = 0
    readonly_fields = ("date_saisie",)


@admin.register(Indicateur)
class IndicateurAdmin(admin.ModelAdmin):
    list_display = ("libelle", "unite", "valeur_cible", "projet", "activite", "frequence_collecte")
    list_filter = ("frequence_collecte",)
    search_fields = ("libelle",)
    inlines = [ValeurIndicateurInline]


@admin.register(ValeurIndicateur)
class ValeurIndicateurAdmin(admin.ModelAdmin):
    list_display = ("indicateur", "periode_debut", "periode_fin", "valeur_realisee", "saisi_par")
    list_filter = ("indicateur",)
    readonly_fields = ("date_saisie",)
