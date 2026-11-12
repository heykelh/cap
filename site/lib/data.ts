// Lecture des données générées par `python -m agents.batch` (dossier site/data).
// Lues au moment de la construction du site : aucune base de données ni IA en production.
import fs from "node:fs";
import path from "node:path";
import { fileKey } from "./files";

const DATA_DIR = path.join(process.cwd(), "data");

export type RadarRow = {
  rang: number;
  iata: string;
  ville: string | null;
  pays: string | null;
  region: string | null;
  score: number | null;
  distance_km: number | null;
  hubs: string | null;
  nb_hubs: number | null;
  pax_hubs: number | null;
  croissance: number | null;
  remplissage: number | null;
  resultat_meur: number;
  marge_pct: number;
  verdict: string;
  alertes: string[];
  lat?: number | null;
  lon?: number | null;
  redige_par_ia?: boolean;
};

export type Fact = { valeur: string; libelle: string; source: string };
export type Alert = { code: string; gravite: "haute" | "moyenne" | "basse"; texte: string };
export type Requete = {
  methode: string;
  sql: string;
  parametres: Record<string, unknown>;
  execute_sur: "BigQuery" | "instantané" | string;
  job_id?: string;
  octets_lus: number;
  octets_factures?: number;
  cache?: boolean;
  duree_ms: number;
  lignes: number;
};
export type Essai = { essai: number | null; brouillon: string | null; rejets: string[]; duree_ms?: number | null };
export type JournalEntry = {
  agent: string;
  statut: string;
  llm?: string;
  rejets?: string[];
  source?: string;
  requetes?: Requete[];
  faits?: Record<string, { valeur: string; libelle: string }>;
  texte?: string;
  duree_ms?: number;
  formules?: { indicateur: string; formule: string; valeur: number }[];
  regles?: { code: string; gravite: string; texte: string }[];
  essais?: Essai[];
  brouillon?: string;
  tentatives?: number;
};
export type Sensitivity = {
  hypothese: string;
  resultat_bas_meur: number;
  resultat_haut_meur: number;
  amplitude_meur: number;
  resultat_base_meur: number;
};

export type Dossier = {
  destination: string;
  note_markdown: string;
  verdict: string;
  alertes: Alert[];
  synthese_economique: Record<string, number | string | null>;
  trace_calcul: { indicateur: string; formule: string; valeur: number }[];
  sensibilites: Sensitivity[];
  faits: Record<string, Fact>;
  journal: JournalEntry[];
  source_donnees: string;
  hypotheses: string;
  limites: string[];
  scenario: { freq: number; aircraft: string; region: string | null };
  opportunity: Record<string, any>;
};

export type Meta = {
  genere_le: string;
  instantane_exporte_le: string | null;
  source_donnees: string | null;
  fraicheur_par_pays: { rep_country: string; last_month: string; share_ok?: number; rows_masked?: number }[];
  hypotheses: {
    version: string;
    valeurs: Record<string, { valeur: number; unite: string; libelle: string; methode: string; source: string }>;
    remplissage_par_region: Record<string, number>;
    appareils: Record<string, { seats: number; cabins?: string; source?: string }>;
    limites: string[];
  };
  llm: string;
  statistiques: { llm: number; gabarit: number; echec: number };
  regle_dossiers?: string;
  radar_par_segment?: Record<string, number>;
  agents_source?: string;
};

export type GcpTable = {
  table: string;
  lignes: number;
  octets: number;
  colonnes: number;
  schema: { nom: string; type: string }[];
  modifiee_le: string | null;
  expire_le: string | null;
};
export type Gcp = {
  genere_le: string;
  projet: string;
  localisation: string;
  datasets: { dataset: string; role: string; tables: GcpTable[] }[];
  requetes_30_jours: { requetes?: number; octets_lus?: number; slot_ms?: number; en_cache?: number; erreur?: string } | null;
  sql: { couche: string; fichier: string; table: string; sql: string }[];
  dernier_rafraichissement: {
    debut: string;
    fin?: string;
    declencheur: string;
    statut: string;
    etapes: { couche: string; etape: string; duree_s: number; statut: string; resume: string }[];
    publication?: string;
  } | null;
};

// Adresse de l'API Cloud Run (vide : le site fonctionne uniquement sur les données exportées).
export const CAP_API = (process.env.NEXT_PUBLIC_CAP_API ?? "").replace(/\/$/, "");

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
}

export function getRadar(): RadarRow[] {
  return readJson<RadarRow[]>("radar.json");
}

export function getMeta(): Meta {
  return readJson<Meta>("meta.json");
}

export function getDossier(iata: string): Dossier | null {
  const file = path.join("dossiers", `${fileKey(iata)}.json`);
  if (!fs.existsSync(path.join(DATA_DIR, file))) return null;
  return readJson<Dossier>(file);
}

export function getGcp(): Gcp | null {
  if (!fs.existsSync(path.join(DATA_DIR, "gcp.json"))) return null;
  return readJson<Gcp>("gcp.json");
}

export function lastPublishedMonth(meta: Meta, country = "FR"): string | null {
  const row = meta.fraicheur_par_pays.find((r) => r.rep_country === country);
  return row?.last_month ?? null;
}
