import { useEffect, useRef, useState } from "react";
import { LocateFixed, Maximize2, Minimize2 } from "lucide-react";
import { ActionIcon, Loader, Stack, Tooltip as Bulle } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Circle, CircleMarker, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";

/**
 * Boutons de la carte, sous le zoom : plein écran (de l'encadré `cible`) et « Ma position »
 * (géolocalisation du navigateur : GPS sur téléphone ; https requis hors localhost).
 */
export function OutilsCarte({ cible }: { cible: HTMLElement | null }) {
  const carte = useMap();
  const boutons = useRef<HTMLDivElement>(null);
  const [pleinEcran, setPleinEcran] = useState(false);
  const [recherche, setRecherche] = useState(false);
  const [position, setPosition] = useState<{ lat: number; lng: number; precision: number } | null>(null);

  // Les clics sur les boutons ne doivent pas déplacer ni zoomer la carte.
  useEffect(() => {
    if (boutons.current) {
      L.DomEvent.disableClickPropagation(boutons.current);
      L.DomEvent.disableScrollPropagation(boutons.current);
    }
  }, []);

  useEffect(() => {
    const changement = () => {
      setPleinEcran(document.fullscreenElement === cible);
      setTimeout(() => carte.invalidateSize(), 150); // la carte prend la nouvelle taille
    };
    document.addEventListener("fullscreenchange", changement);
    return () => document.removeEventListener("fullscreenchange", changement);
  }, [carte, cible]);

  function basculerPleinEcran() {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void cible?.requestFullscreen?.();
  }

  function localiser() {
    if (!navigator.geolocation) {
      notifications.show({ message: "Votre navigateur ne permet pas la géolocalisation.", color: "orange" });
      return;
    }
    setRecherche(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setRecherche(false);
        const ici = { lat: p.coords.latitude, lng: p.coords.longitude, precision: p.coords.accuracy };
        setPosition(ici);
        carte.flyTo([ici.lat, ici.lng], Math.max(carte.getZoom(), ici.precision > 5000 ? 10 : 14));
      },
      (erreur) => {
        setRecherche(false);
        notifications.show({
          message: erreur.code === erreur.PERMISSION_DENIED
            ? "Position refusée : autorisez la localisation pour ce site dans votre navigateur."
            : "Position introuvable pour le moment (GPS désactivé ou signal faible).",
          color: "orange",
        });
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
    );
  }

  return (
    <>
      <div ref={boutons} style={{ position: "absolute", top: 80, left: 10, zIndex: 1000 }}>
        <Stack gap={4}>
          <Bulle label={pleinEcran ? "Quitter le plein écran" : "Plein écran"} position="right">
            <ActionIcon variant="default" size="lg" onClick={basculerPleinEcran} aria-label="Plein écran">
              {pleinEcran ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </ActionIcon>
          </Bulle>
          <Bulle label="Ma position" position="right">
            <ActionIcon variant="default" size="lg" onClick={localiser} aria-label="Ma position">
              {recherche ? <Loader size={14} /> : <LocateFixed size={16} />}
            </ActionIcon>
          </Bulle>
        </Stack>
      </div>
      {position && (
        <>
          <Circle center={[position.lat, position.lng]} radius={position.precision} pathOptions={{ color: "#1c7ed6", weight: 1, fillOpacity: 0.1 }} interactive={false} />
          <CircleMarker center={[position.lat, position.lng]} radius={8} pathOptions={{ color: "#fff", weight: 3, fillColor: "#1c7ed6", fillOpacity: 1 }}>
            <Tooltip direction="top" permanent>Vous êtes ici (± {Math.round(position.precision)} m)</Tooltip>
          </CircleMarker>
        </>
      )}
    </>
  );
}
