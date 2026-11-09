import { voc } from "./vocabulaire";

export const GO = 1024 ** 3;

/** « 3,25 Go », « 640 Mo » (octets lisibles) ; arrondi vers le bas : 50 Go moins 18 Mo donne « 49,98 Go », pas « 50 Go ». */
export const volumeLisible = (octets: number) =>
  octets >= GO ? voc`${(Math.floor((octets / GO) * 100) / 100).toLocaleString(undefined, { maximumFractionDigits: 2 })} Go`
    : voc`${Math.max(octets > 0 ? 1 : 0, Math.round(octets / 1024 ** 2))} Mo`;
