-- Une ligne par route (aéroport déclarant, aéroport partenaire) et par mois.
-- Passagers, sièges et vols côte à côte, enrichis des codes IATA, des villes et de la distance.
-- Une valeur confidentielle Eurostat (valeur vide) est conservée et signalée 'valeur_masquee' :
-- la route existe ce mois-là, seul son volume est masqué.
-- Attention : une route intra-déclarante (ex. CDG - Francfort) apparaît deux fois,
-- une fois déclarée par la France, une fois par l'Allemagne. Le choix du côté se fait en gold.
WITH pivot AS (
  SELECT
    rep_country,
    rep_icao,
    partner_country,
    partner_icao,
    period,
    SUM(IF(measure = 'PAS_BRD', value, NULL)) AS passengers,
    SUM(IF(measure = 'ST_PAS', value, NULL)) AS seats,
    SUM(IF(measure = 'CAF_PAS', value, NULL)) AS flights,
    COUNTIF(value IS NULL) AS masked_measures,
    ANY_VALUE(dataset_code) AS dataset_code,
    MAX(_ingested_at) AS ingested_at
  FROM `cap_bronze.eurostat_routes`
  GROUP BY rep_country, rep_icao, partner_country, partner_icao, period
)
SELECT
  PARSE_DATE('%Y-%m-%d', CONCAT(p.period, '-01')) AS month,
  p.rep_country,
  p.rep_icao,
  r.iata AS rep_iata,
  r.city AS rep_city,
  p.partner_country,
  p.partner_icao,
  a.iata AS partner_iata,
  a.city AS partner_city,
  a.airport_name AS partner_airport,
  CAST(p.passengers AS INT64) AS passengers,
  CAST(p.seats AS INT64) AS seats,
  CAST(p.flights AS INT64) AS flights,
  ROUND(SAFE_DIVIDE(p.passengers, p.seats), 4) AS load_factor,
  ROUND(SAFE_DIVIDE(p.seats, p.flights), 1) AS seats_per_flight,
  ROUND(ST_DISTANCE(r.geo, a.geo) / 1000) AS distance_km,
  CASE
    WHEN r.icao IS NULL OR a.icao IS NULL THEN 'aeroport_inconnu'
    WHEN p.masked_measures > 0 THEN 'valeur_masquee'
    WHEN p.seats IS NULL OR p.seats = 0 THEN 'sieges_absents'
    WHEN SAFE_DIVIDE(p.passengers, p.seats) > 1 THEN 'remplissage_sup_100'
    ELSE 'ok'
  END AS quality_flag,
  p.dataset_code,
  p.ingested_at
FROM pivot AS p
LEFT JOIN `cap_silver.airports` AS r ON r.icao = p.rep_icao
LEFT JOIN `cap_silver.airports` AS a ON a.icao = p.partner_icao
