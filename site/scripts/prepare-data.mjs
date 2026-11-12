// Prépare les données du site avant « npm run dev » et « npm run build ».
//  1. Si CAP_DATA_URL est défini (paquet publié chaque mois sur Cloud Storage par le job de
//     rafraîchissement), télécharge les données les plus récentes. Sinon, garde celles du dépôt.
//  2. Copie les dossiers et les sessions enregistrées des agents IA dans public/ pour le mode « Rejouer ».
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const url = process.env.CAP_DATA_URL;

if (url) {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const bundle = await res.json();
    let n = 0;
    for (const [rel, content] of Object.entries(bundle)) {
      if (!/^(data|public\/marche)\/[\w\-./]+\.json$/.test(rel) || rel.includes("..")) continue;
      const file = path.join(root, rel);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, JSON.stringify(content));
      n++;
    }
    console.log(`Données à jour : ${n} fichiers téléchargés depuis ${url}`);
  } catch (err) {
    console.warn(`Téléchargement impossible (${err.message}) : données du dépôt conservées.`);
  }
}

function copyJson(from, to) {
  const src = path.join(root, ...from);
  const dst = path.join(root, ...to);
  fs.mkdirSync(dst, { recursive: true });
  let n = 0;
  if (fs.existsSync(src)) {
    for (const f of fs.readdirSync(src)) {
      if (f.endsWith(".json")) {
        fs.copyFileSync(path.join(src, f), path.join(dst, f));
        n++;
      }
    }
  }
  return n;
}
console.log(`Dossiers prêts pour la chaîne d'instruction : ${copyJson(["data", "dossiers"], ["public", "dossiers"])}`);
console.log(`Sessions des agents IA prêtes : ${copyJson(["data", "analyste"], ["public", "analyste"])}`);
