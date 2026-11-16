import { useEffect, useRef, useState } from "react";
import { Input } from "@mantine/core";
import { langue } from "../../utils/i18n";
import { voc } from "../../utils/vocabulaire";

type Recaptcha = {
  render: (cible: HTMLElement, options: { sitekey: string; callback: (jeton: string) => void; "expired-callback": () => void }) => number;
};
declare global {
  interface Window { grecaptcha?: Recaptcha; monitoraRecaptchaApp?: () => void }
}

let chargement: Promise<void> | null = null;

/** Charge une seule fois le script de Google reCAPTCHA (rendu à la demande). */
function chargerRecaptcha(): Promise<void> {
  chargement ??= new Promise((resolu, rejete) => {
    window.monitoraRecaptchaApp = () => resolu();
    const script = document.createElement("script");
    script.src = `https://www.google.com/recaptcha/api.js?onload=monitoraRecaptchaApp&render=explicit&hl=${encodeURIComponent(langue())}`;
    script.async = true;
    script.onerror = () => { chargement = null; rejete(new Error("recaptcha")); };
    document.head.appendChild(script);
  });
  return chargement;
}

/**
 * Case « Je ne suis pas un robot » : `onJeton` reçoit le jeton une fois la case cochée ("" s'il expire).
 * Un jeton ne sert qu'une fois : après un refus du serveur, changer la `key` du composant pour une case neuve.
 */
export function CaseRobot({ cle, onJeton, error }: { cle: string; onJeton: (jeton: string) => void; error?: string }) {
  const zone = useRef<HTMLDivElement>(null);
  const rappel = useRef(onJeton);
  rappel.current = onJeton;
  // Script de Google bloqué (bloqueur de publicité, réseau filtré) : la case ne peut pas s'afficher.
  const [bloque, setBloque] = useState(false);

  useEffect(() => {
    let annule = false;
    rappel.current("");
    setBloque(false);
    const delai = window.setTimeout(() => { if (!annule) setBloque(true); }, 10000);
    chargerRecaptcha().then(() => {
      window.clearTimeout(delai);
      if (annule || !zone.current || !window.grecaptcha) return;
      const cible = document.createElement("div");
      zone.current.replaceChildren(cible);
      window.grecaptcha.render(cible, {
        sitekey: cle, callback: (jeton) => rappel.current(jeton), "expired-callback": () => rappel.current(""),
      });
    }).catch(() => { window.clearTimeout(delai); if (!annule) setBloque(true); });
    return () => { annule = true; window.clearTimeout(delai); };
  }, [cle]);

  return (
    <div>
      <div ref={zone} style={{ minHeight: 78 }} />
      {bloque && (
        <Input.Error mt={4}>
          {voc("La case « Je ne suis pas un robot » n'a pas pu s'afficher. Désactivez le bloqueur de publicité pour ce site ou vérifiez votre connexion, puis rechargez la page.")}
        </Input.Error>
      )}
      {error && <Input.Error mt={4}>{error}</Input.Error>}
    </div>
  );
}
