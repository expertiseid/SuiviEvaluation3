"""
Progression de chaque utilisateur dans le cours en ligne (base de son organisation). Le contenu du cours
(modules, leçons, quiz) est le même pour tous et vient de contenu.py.
"""
from django.conf import settings
from django.db import models


class LeconTerminee(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lecons_terminees")
    lecon = models.CharField(max_length=60)
    terminee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("utilisateur", "lecon"), name="lecon_terminee_unique")]


class TentativeQuiz(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tentatives_quiz")
    module = models.CharField(max_length=60)
    score = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    reussi = models.BooleanField()
    reponses = models.JSONField(default=list)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date",)


class Attestation(models.Model):
    """Délivrée une fois tous les quiz réussis ; son numéro permet de la vérifier."""

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attestation_formation")
    numero = models.CharField(max_length=20, unique=True)
    delivree_le = models.DateTimeField(auto_now_add=True)
