"""
Musique de fond des vidéos (30 s), composée ici : pas de droits à payer. Nappe d'accords, basse, arpège
doux, percussions légères ; un « whoosh » à chaque changement de scène (scenes.json). WAV stéréo 44,1 kHz.
"""
import json
import os
import wave

import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUREE = 30.0
N = int(SR * DUREE)
t_tout = np.arange(N) / SR

NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def freq(nom, octave):
    return 440.0 * 2 ** ((NOTES[nom] + 12 * (octave + 1) - 69) / 12)


ACCORDS = {"Am": ["A", "C", "E"], "F": ["F", "A", "C"], "C": ["C", "E", "G"], "G": ["G", "B", "D"],
           "Em": ["E", "G", "B"], "Dm": ["D", "F", "A"]}

STYLES = {
    # tempo, progression, force des percussions, départ des percussions (s), arpège
    "lancement": dict(tempo=104, accords=["Am", "F", "C", "G"], perc=1.0, depart_perc=4.5, arpege=True),
    "presentation": dict(tempo=92, accords=["C", "G", "Am", "F"], perc=0.55, depart_perc=3.5, arpege=True),
    "offres": dict(tempo=112, accords=["F", "C", "G", "Am"], perc=0.85, depart_perc=7.5, arpege=True),
}


def enveloppe(n, attaque, relache):
    e = np.ones(n)
    a, r = min(n, int(attaque * SR)), min(n, int(relache * SR))
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def passe_bas(x, force):
    """Filtre passe-bas à un pôle (son plus doux)."""
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += force * (x[i] - acc)
        y[i] = acc
    return y


def nappe(f, n):
    t = np.arange(n) / SR
    s = np.zeros(n)
    for desaccord in (-0.12, 0.0, 0.13):  # trois voix légèrement désaccordées
        ff = f * 2 ** (desaccord / 12)
        for h in range(1, 7):
            s += np.sin(2 * np.pi * ff * h * t) / h ** 1.6
    return s / 6


def ajouter(piste, signal, debut):
    i = int(debut * SR)
    if i >= len(piste):
        return
    fin = min(len(piste), i + len(signal))
    piste[i:fin] += signal[: fin - i]


def composer(nom):
    st = STYLES[nom]
    temps = 60.0 / st["tempo"]
    mesure = 4 * temps
    g = np.zeros(N)
    d = np.zeros(N)

    # Nappe : un accord par mesure, enchaînés en fondu.
    nb_mesures = int(np.ceil(DUREE / mesure)) + 1
    for m in range(nb_mesures):
        accord = ACCORDS[st["accords"][m % len(st["accords"])]]
        n = int((mesure + 0.6) * SR)
        son = sum(nappe(freq(note, 3 if k else 3), n) for k, note in enumerate(accord))
        son += 0.5 * nappe(freq(accord[0], 4), n)
        son *= enveloppe(n, 0.5, 0.7) * 0.11
        ajouter(g, son, m * mesure)
        ajouter(d, son * 0.92, m * mesure + 0.012)

        # Basse : croches sur la fondamentale.
        racine = freq(accord[0], 1)
        for c in range(8):
            debut = m * mesure + c * temps / 2
            if debut < 1.0:
                continue
            nn = int(temps / 2 * SR)
            tt = np.arange(nn) / SR
            b = (np.sin(2 * np.pi * racine * tt) + 0.3 * np.sin(2 * np.pi * racine * 2 * tt)) * np.exp(-tt * 7) * 0.22
            ajouter(g, b, debut)
            ajouter(d, b, debut)

        # Arpège : notes de l'accord en croches, timbre « pluck ».
        if st["arpege"]:
            ordre = [0, 1, 2, 1, 0, 2, 1, 2]
            for c, k in enumerate(ordre):
                debut = m * mesure + c * temps / 2
                if debut < 2.0:
                    continue
                f = freq(accord[k], 5)
                nn = int(0.45 * SR)
                tt = np.arange(nn) / SR
                p = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 9) * 0.07
                pan = 0.3 + 0.4 * (k / 2)
                ajouter(g, p * (1 - pan) * 2, debut)
                ajouter(d, p * pan * 2, debut + 0.004)

    # Percussions : grosse caisse sur chaque temps, charleston sur les contretemps.
    battement = st["depart_perc"]
    while battement < DUREE - 1.2:
        nn = int(0.35 * SR)
        tt = np.arange(nn) / SR
        kick = np.sin(2 * np.pi * (48 + 70 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 9) * 0.5 * st["perc"]
        ajouter(g, kick, battement)
        ajouter(d, kick, battement)
        nh = int(0.05 * SR)
        hat = np.random.default_rng(int(battement * 1000)).standard_normal(nh)
        hat = np.diff(hat, prepend=0) * np.exp(-np.arange(nh) / SR * 70) * 0.035 * st["perc"]
        ajouter(g, hat * 0.7, battement + temps / 2)
        ajouter(d, hat, battement + temps / 2)
        battement += temps

    # Whoosh à chaque changement de scène (bruit filtré qui monte puis s'éteint).
    rng = np.random.default_rng(7)
    for (debut, _fin) in list(json.load(open(f"{ICI}/scenes.json"))[nom]["scenes"].values())[1:]:
        nn = int(0.9 * SR)
        bruit = rng.standard_normal(nn)
        bruit = passe_bas(bruit, 0.18)
        forme = np.concatenate([np.linspace(0, 1, int(0.65 * SR)) ** 2, np.linspace(1, 0, nn - int(0.65 * SR)) ** 0.5])
        w = bruit * forme * 0.28
        ajouter(g, w, debut - 0.65)
        ajouter(d, w[::-1] * 0.2 + w * 0.8, debut - 0.65)

    # Accord final qui résonne, et fondu.
    fin = np.ones(N)
    k = int(1.4 * SR)
    fin[-k:] = np.linspace(1, 0, k) ** 1.5
    fin[: int(0.3 * SR)] = np.linspace(0, 1, int(0.3 * SR))
    stereo = np.stack([g * fin, d * fin], axis=1)
    stereo = passe_bas_stereo(stereo)
    stereo *= 0.7 / np.max(np.abs(stereo))
    return stereo


def passe_bas_stereo(x):
    return np.stack([passe_bas(x[:, 0], 0.55), passe_bas(x[:, 1], 0.55)], axis=1)


def ecrire(fichier, stereo):
    donnees = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(fichier, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(donnees.tobytes())


if __name__ == "__main__":
    os.makedirs(f"{ICI}/musique", exist_ok=True)
    for nom in STYLES:
        ecrire(f"{ICI}/musique/{nom}.wav", composer(nom))
        print(nom, "ok")
