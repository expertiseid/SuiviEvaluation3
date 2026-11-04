from django.urls import path

from . import views

urlpatterns = [
    path("formation/", views.sommaire, name="formation"),
    path("formation/modules/<str:module>/lecons/<str:code>/", views.lecon, name="formation-lecon"),
    path("formation/modules/<str:module>/quiz/", views.quiz, name="formation-quiz"),
    path("formation/attestation/", views.attestation, name="formation-attestation"),
]
