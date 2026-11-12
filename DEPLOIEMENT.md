# Déployer CAP sur Google Cloud

Objectif : l'API en direct sur **Cloud Run**, le rafraîchissement mensuel en **Cloud Run Job**
déclenché par **Cloud Scheduler**, les clés d'IA dans **Secret Manager**, les données du site sur
**Cloud Storage**, le site sur **Vercel**.

Toutes les commandes se lancent dans PowerShell, depuis le dossier `cap`. Projet : `cap-network`,
région : `europe-west1` (Belgique, proche des données BigQuery en `EU`).

---

## 0. Facturation et budget (une fois)

1. Console GCP → **Facturation** → associer un compte de facturation au projet `cap-network`.
2. **Facturation → Budgets et alertes** → créer un budget de **5 €** par mois, alertes à 50 %, 90 %, 100 %.
3. Retirer l'expiration des tables existantes (sinon elles disparaissent au bout de 60 jours) :

```powershell
python -m ops.remove_expiration
```

## 1. Activer les services

```powershell
gcloud config set project cap-network
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com storage.googleapis.com
```

## 2. Compte de service à privilèges minimaux

```powershell
gcloud iam service-accounts create cap-runner --display-name "CAP (API et rafraîchissement)"
$SA = "cap-runner@cap-network.iam.gserviceaccount.com"
foreach ($role in "roles/bigquery.dataEditor", "roles/bigquery.jobUser", "roles/bigquery.resourceViewer", "roles/secretmanager.secretAccessor", "roles/run.invoker") {
  gcloud projects add-iam-policy-binding cap-network --member "serviceAccount:$SA" --role $role --condition=None
}
```

`bigquery.resourceViewer` sert à l'inventaire (historique des requêtes) de la page « Sous le capot ».

## 3. Secrets (clés d'IA)

```powershell
"TA_CLE_GROQ" | Out-File -NoNewline -Encoding ascii groq.txt
gcloud secrets create groq-api-key --data-file groq.txt
"TA_CLE_GEMINI" | Out-File -NoNewline -Encoding ascii gemini.txt
gcloud secrets create gemini-api-key --data-file gemini.txt
Remove-Item groq.txt, gemini.txt
```

## 4. Bucket des données du site

```powershell
gcloud storage buckets create gs://cap-network-site --location EU --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://cap-network-site --member allUsers --role roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding gs://cap-network-site --member "serviceAccount:$SA" --role roles/storage.objectAdmin
```

Le bucket ne contient que les données publiques du site (dossiers, études, inventaire).

## 5. Construire l'image

```powershell
gcloud artifacts repositories create cap --repository-format docker --location europe-west1
gcloud builds submit --tag europe-west1-docker.pkg.dev/cap-network/cap/cap:latest
```

## 6. Déployer l'API (Cloud Run service)

```powershell
gcloud run deploy cap-api `
  --image europe-west1-docker.pkg.dev/cap-network/cap/cap:latest `
  --region europe-west1 --service-account $SA --allow-unauthenticated `
  --memory 1Gi --cpu 1 --max-instances 2 --timeout 300 `
  --set-env-vars GCP_PROJECT_ID=cap-network,BQ_LOCATION=EU,CAP_LLM=groq,gemini `
  --set-secrets GROQ_API_KEY=groq-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest
```

Attention : `CAP_LLM=groq,gemini` contient une virgule. Si gcloud se plaint, remplace par
`--set-env-vars "^;^GCP_PROJECT_ID=cap-network;BQ_LOCATION=EU;CAP_LLM=groq,gemini"`.

La commande affiche l'adresse du service, du type `https://cap-api-xxxxx-ew.a.run.app`. Vérifie :

```powershell
curl.exe "https://cap-api-xxxxx-ew.a.run.app/health?bigquery=1"
curl.exe "https://cap-api-xxxxx-ew.a.run.app/marche/JFK"
```

## 7. Le rafraîchissement mensuel (Cloud Run Job + Cloud Scheduler)

Crée d'abord un crochet de déploiement dans Vercel (étape 8), puis :

```powershell
gcloud run jobs create cap-refresh `
  --image europe-west1-docker.pkg.dev/cap-network/cap/cap:latest `
  --region europe-west1 --service-account $SA `
  --command python --args "-m,pipeline.refresh" `
  --task-timeout 3h --max-retries 0 --memory 2Gi --cpu 1 `
  --set-env-vars "^;^GCP_PROJECT_ID=cap-network;BQ_LOCATION=EU;CAP_LLM=groq,gemini;CAP_SITE_BUCKET=cap-network-site;VERCEL_DEPLOY_HOOK=https://api.vercel.com/v1/integrations/deploy/XXXX" `
  --set-secrets GROQ_API_KEY=groq-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest

gcloud scheduler jobs create http cap-refresh-mensuel `
  --location europe-west1 --schedule "0 6 5 * *" --time-zone "Europe/Paris" `
  --uri "https://run.googleapis.com/v2/projects/cap-network/locations/europe-west1/jobs/cap-refresh:run" `
  --http-method POST --oauth-service-account-email $SA
```

Premier lancement à la main, pour vérifier (environ 40 minutes) :

```powershell
gcloud run jobs execute cap-refresh --region europe-west1
```

Suivi : Console GCP → Cloud Run → Jobs → cap-refresh → Journaux.

## 8. Vercel

Dans le projet Vercel (dossier racine `site`) → **Settings → Environment Variables** :

| Variable | Valeur |
|---|---|
| `NEXT_PUBLIC_CAP_API` | l'adresse Cloud Run de l'étape 6 (sans `/` final) |
| `CAP_DATA_URL` | `https://storage.googleapis.com/cap-network-site/cap-site-data.json` |

Puis **Settings → Git → Deploy Hooks** : créer un crochet (branche `main`) et copier son adresse
dans `VERCEL_DEPLOY_HOOK` (étape 7). Redéployer une fois.

## Mettre à jour le code plus tard

```powershell
gcloud builds submit --tag europe-west1-docker.pkg.dev/cap-network/cap/cap:latest
gcloud run deploy cap-api --image europe-west1-docker.pkg.dev/cap-network/cap/cap:latest --region europe-west1
gcloud run jobs update cap-refresh --image europe-west1-docker.pkg.dev/cap-network/cap/cap:latest --region europe-west1
```

## Coûts attendus

Cloud Run ne facture que le temps d'exécution réel (arrêté sans visiteur), BigQuery lit quelques
mégaoctets par requête, le job tourne moins d'une heure par mois. Ordre de grandeur : quelques
centimes à quelques euros par mois. L'API se protège elle-même : 8 demandes par visiteur toutes les
10 minutes (`CAP_LIMIT_PER_10MIN`), 2 instances au plus.
