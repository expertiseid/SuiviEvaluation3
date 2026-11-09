import { voc } from "./vocabulaire";

export const GO = 1024 ** 3;

/** « 3,2 Go », « 640 Mo » (octets lisibles). */
export const volumeLisible = (octets: number) =>
  octets >= GO ? voc`${(octets / GO).toLocaleString(undefined, { maximumFractionDigits: 1 })} Go`
    : voc`${Math.max(octets > 0 ? 1 : 0, Math.round(octets / 1024 ** 2))} Mo`;
