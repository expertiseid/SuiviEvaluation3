from django.contrib import admin

from .models import Activite, Equipe, NiveauActivite, Projet, SousActivite


class NiveauActiviteInline(admin.TabularInline):
    model = NiveauActivite
    extra = 0


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "statut", "type_mise_en_oeuvre", "chef_de_projet_nom", "date_debut", "date_fin", "budget_total")
    list_filter = ("statut", "type_mise_en_oeuvre", "partenaire_bailleur", "cadre_strategique")
    search_fields = ("code", "nom")
    filter_horizontal = ("zones", "utilisateurs_affectes")
    inlines = [NiveauActiviteInline]


class SousActiviteInline(admin.TabularInline):
    model = SousActivite
    extra = 0


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ("code_activite", "libelle", "projet", "activite_parent", "statut", "responsable", "budget_alloue", "budget_realise")
    list_filter = ("projet", "statut", "equipe_responsable")
    inlines = [SousActiviteInline]


@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    search_fields = ("nom",)


@admin.register(SousActivite)
class SousActiviteAdmin(admin.ModelAdmin):
    list_display = ("libelle", "activite", "statut", "date_debut", "date_fin")
    list_filter = ("statut",)
