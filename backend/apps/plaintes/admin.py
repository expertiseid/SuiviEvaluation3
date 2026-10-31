from django.contrib import admin

from .models import Categorie, Circuit, EtapeCircuit, Mecanisme, Priorite, TypeRetour

admin.site.register([Mecanisme, TypeRetour, Priorite, Circuit, EtapeCircuit, Categorie])
