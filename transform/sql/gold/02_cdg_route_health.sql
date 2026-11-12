-- Bilan de santé des lignes exploitées au départ de CDG.
-- Toutes compagnies confondues : Eurostat ne détaille pas par transporteur.
SELECT
  partner_icao,
  partner_iata,
  partner_city,
  partner_airport,
  partner_country,
  distance_km,
  CASE
    WHEN distance_km >= 4000 THEN 'long-courrier'
    WHEN distance_km >= 1500 THEN 'moyen-courrier'
    ELSE 'court-courrier'
  END AS segment,
  flights_l12,
  seats_l12,
  pax_l12,
  lf_l12,
  pax_p12,
  lf_p12,
  growth_pax,
  growth_seats,
  ROUND((lf_l12 - lf_p12) * 100, 1) AS lf_delta_pts,
  CASE
    WHEN masked_months_l12 >= 6 THEN 'donnees_masquees'
    WHEN growth_pax < -0.05 THEN 'trafic_en_baisse'
    WHEN (lf_l12 - lf_p12) * 100 < -3 THEN 'remplissage_en_baisse'
    WHEN lf_l12 < 0.70 THEN 'remplissage_faible'
    WHEN growth_seats > 0.10 AND (lf_l12 - lf_p12) * 100 < 0 THEN 'capacite_en_avance_sur_demande'
    ELSE 'ras'
  END AS alert,
  months_l12,
  masked_months_l12,
  window_end,
  flagged_months_l12
FROM `cap_gold.route_window`
WHERE rep_icao = 'LFPG'
  -- Ligne exploitée : au moins un vol par semaine en moyenne, ou volumes masqués par
  -- Eurostat au moins 10 mois sur 12 (la route existe, son volume n'est pas publié).
  AND (flights_l12 >= 52 OR masked_months_l12 >= 10)
