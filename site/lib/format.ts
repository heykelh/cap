// Formatage à la française.
const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const int = (x: number | null | undefined) => (x == null ? "n.d." : nf0.format(Math.round(x)));
export const meur = (eur: number) => `${nf1.format(eur / 1e6)} M€`;
export const meurFromM = (m: number | null | undefined) => (m == null ? "n.d." : `${nf1.format(m)} M€`);
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "n.d." : `${new Intl.NumberFormat("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x * 100)} %`;
export const signedPct = (x: number | null | undefined) =>
  x == null ? "n.d." : `${x >= 0 ? "+" : "−"}${nf1.format(Math.abs(x * 100))} %`;
export const km = (x: number | null | undefined) => (x == null ? "n.d." : `${nf0.format(x)} km`);

const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
  "octobre", "novembre", "décembre"];

export function month(iso: string | null | undefined) {
  if (!iso) return "n.d.";
  const [y, m] = iso.slice(0, 7).split("-").map(Number);
  return `${MOIS[m - 1]} ${y}`;
}

export function day(iso: string | null | undefined) {
  if (!iso) return "n.d.";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MOIS[m - 1]} ${y}`;
}

export function verdictTone(verdict: string): "go" | "watch" | "stop" {
  if (verdict.startsWith("ne pas")) return "stop";
  if (verdict.startsWith("approfondir")) return "watch";
  return "go";
}

export function verdictShort(verdict: string) {
  return verdict.split(" :")[0];
}

export const ALERT_LABELS: Record<string, string> = {
  part_marche_elevee: "Part de marché à conquérir élevée",
  deficitaire: "Ligne déficitaire",
  marge_fine: "Marge fine",
  dependance_yield: "Très sensible au prix des billets",
  yield_long_courrier: "Recette probablement optimiste",
  hub_unique: "Demande observée sur un seul hub",
  hub_dominant: "Un hub domine la demande",
  demande_en_baisse: "Demande en baisse",
  donnees_anciennes: "Données à actualiser",
  donnees_masquees: "Données partiellement masquées",
  desserte_marginale: "Déjà desservie ponctuellement",
  marche_surveille: "Marché sous surveillance",
  desserte_a_verifier: "Desserte actuelle à vérifier",
};
