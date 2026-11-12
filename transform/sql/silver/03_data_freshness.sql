-- Fraîcheur et qualité des données par pays déclarant.
-- Sert au badge « données au … » du site et au suivi de qualité.
SELECT
  rep_country,
  MIN(month) AS first_month,
  MAX(month) AS last_month,
  COUNT(DISTINCT rep_icao) AS airports,
  COUNT(*) AS route_months,
  COUNTIF(quality_flag = 'ok') AS rows_ok,
  COUNTIF(quality_flag = 'aeroport_inconnu') AS rows_unknown_airport,
  COUNTIF(quality_flag = 'valeur_masquee') AS rows_masked,
  COUNTIF(quality_flag = 'sieges_absents') AS rows_missing_seats,
  COUNTIF(quality_flag = 'remplissage_sup_100') AS rows_lf_over_100,
  ROUND(SAFE_DIVIDE(COUNTIF(quality_flag = 'ok'), COUNT(*)), 4) AS share_ok
FROM `cap_silver.routes_monthly`
GROUP BY rep_country
