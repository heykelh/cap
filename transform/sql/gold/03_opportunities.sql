-- Radar d'opportunités : destinations reliées en direct depuis les grands hubs européens
-- concurrents, mais ni depuis CDG ni depuis Orly.
--
-- Règles :
--   * seules les routes régulières des hubs comptent (au moins 52 vols sur 12 mois) ;
--   * les vols intérieurs d'un hub sont exclus (ex. Madrid - Las Palmas), sinon
--     ils écraseraient le classement ;
--   * les destinations en France sont exclues, ainsi que les villes déjà desservies
--     depuis Paris et les lignes signalées par l'analyste (reference/paris_network_overrides.csv) ;
--   * score transparent de 0 à 100, calculé à l'intérieur de chaque segment
--     (court, moyen, long-courrier) : volume 40 %, croissance 25 %,
--     remplissage 20 %, nombre de hubs qui desservent 15 %.
WITH hubs AS (
  SELECT icao
  FROM UNNEST([
    'EHAM', 'EDDF', 'EDDM', 'LEMD', 'LEBL', 'LIRF', 'LSZH', 'LOWW', 'EBBR',
    'EKCH', 'LTFM', 'LPPT', 'EIDW', 'ESSA', 'ENGM', 'EFHK'
  ]) AS icao
),
hub_flows AS (
  SELECT w.*
  FROM `cap_gold.route_window` AS w
  JOIN hubs AS h ON h.icao = w.rep_icao
  WHERE w.partner_country != w.rep_country
    AND w.partner_country != 'FR'
    AND w.flights_l12 >= 52
),
paris AS (
  SELECT
    partner_icao,
    SUM(IF(rep_icao = 'LFPG', flights_l12, 0)) AS cdg_flights_l12,
    SUM(IF(rep_icao = 'LFPG', masked_months_l12, 0)) AS cdg_masked_months_l12,
    SUM(IF(rep_icao = 'LFPO', flights_l12, 0)) AS ory_flights_l12,
    SUM(IF(rep_icao = 'LFPO', masked_months_l12, 0)) AS ory_masked_months_l12
  FROM `cap_gold.route_window`
  WHERE rep_icao IN ('LFPG', 'LFPO')
  GROUP BY partner_icao
),
-- Villes déjà desservies depuis Paris, tous aéroports confondus.
-- Couvre les villes à plusieurs aéroports et les anciens codes (ex. Doha DIA / DOH).
paris_cities AS (
  SELECT DISTINCT ap.city, ap.country_iso2
  FROM `cap_gold.route_window` AS w
  JOIN `cap_silver.airports` AS ap ON ap.icao = w.partner_icao
  WHERE w.rep_icao IN ('LFPG', 'LFPO')
    AND (w.flights_l12 >= 52 OR w.masked_months_l12 >= 10)
    AND ap.city IS NOT NULL
),
-- Corrections de l'analyste : lignes desservies que les statistiques ne voient pas
-- (lignes saisonnières, routes non publiées par Eurostat). Chaque ligne cite sa source.
overrides AS (
  SELECT DISTINCT partner_iata
  FROM `cap_bronze.paris_network_overrides`
  WHERE status = 'desservie'
),
agg AS (
  SELECT
    partner_icao,
    ANY_VALUE(partner_iata) AS partner_iata,
    ANY_VALUE(partner_city) AS partner_city,
    ANY_VALUE(partner_airport) AS partner_airport,
    ANY_VALUE(partner_country) AS partner_country,
    COUNT(*) AS hubs_serving,
    STRING_AGG(COALESCE(rep_iata, rep_icao), ', ' ORDER BY pax_l12 DESC) AS hubs_list,
    SUM(pax_l12) AS pax_l12_hubs,
    SUM(pax_p12) AS pax_p12_hubs,
    SUM(seats_l12) AS seats_l12_hubs,
    SUM(flights_l12) AS flights_l12_hubs,
    ROUND(SAFE_DIVIDE(SUM(pax_with_seats_l12), SUM(seats_l12)), 4) AS lf_l12_hubs,
    MIN(window_end) AS data_until_min,
    MAX(window_end) AS data_until_max
  FROM hub_flows
  GROUP BY partner_icao
),
base AS (
  SELECT
    a.*,
    IF(a.pax_p12_hubs >= 1000, ROUND(SAFE_DIVIDE(a.pax_l12_hubs, a.pax_p12_hubs) - 1, 4), NULL)
      AS growth_hubs,
    ROUND(ST_DISTANCE(cdg.geo, p.geo) / 1000) AS distance_from_cdg_km,
    COALESCE(x.cdg_flights_l12, 0) AS cdg_flights_l12,
    COALESCE(x.cdg_masked_months_l12, 0) AS cdg_masked_months_l12,
    COALESCE(x.ory_flights_l12, 0) AS ory_flights_l12,
    COALESCE(x.ory_masked_months_l12, 0) AS ory_masked_months_l12
  FROM agg AS a
  LEFT JOIN `cap_silver.airports` AS p ON p.icao = a.partner_icao
  CROSS JOIN (SELECT geo FROM `cap_silver.airports` WHERE icao = 'LFPG') AS cdg
  LEFT JOIN paris AS x ON x.partner_icao = a.partner_icao
  LEFT JOIN paris_cities AS pc ON pc.city = p.city AND pc.country_iso2 = p.country_iso2
  LEFT JOIN overrides AS o ON o.partner_iata = a.partner_iata
  -- Paris ne dessert pas la destination :
  --   * ni CDG ni Orly n'ont de ligne régulière vers cet aéroport (au moins 52 vols
  --     sur 12 mois, ou volumes masqués par Eurostat au moins 10 mois sur 12) ;
  --   * Paris ne dessert pas déjà la même ville par un autre aéroport ;
  --   * l'analyste n'a pas signalé la ligne comme desservie.
  WHERE COALESCE(x.cdg_flights_l12, 0) < 52
    AND COALESCE(x.cdg_masked_months_l12, 0) < 10
    AND COALESCE(x.ory_flights_l12, 0) < 52
    AND COALESCE(x.ory_masked_months_l12, 0) < 10
    AND pc.city IS NULL
    AND o.partner_iata IS NULL
    AND a.pax_l12_hubs >= 50000
),
segmented AS (
  SELECT
    *,
    CASE
      WHEN distance_from_cdg_km >= 4000 THEN 'long-courrier'
      WHEN distance_from_cdg_km >= 1500 THEN 'moyen-courrier'
      ELSE 'court-courrier'
    END AS segment
  FROM base
),
scored AS (
  SELECT
    *,
    PERCENT_RANK() OVER (PARTITION BY segment ORDER BY pax_l12_hubs) AS s_volume,
    PERCENT_RANK() OVER (PARTITION BY segment ORDER BY COALESCE(growth_hubs, 0)) AS s_growth,
    PERCENT_RANK() OVER (PARTITION BY segment ORDER BY COALESCE(lf_l12_hubs, 0)) AS s_lf,
    PERCENT_RANK() OVER (PARTITION BY segment ORDER BY hubs_serving) AS s_hubs
  FROM segmented
)
SELECT
  *,
  ROUND(100 * (0.40 * s_volume + 0.25 * s_growth + 0.20 * s_lf + 0.15 * s_hubs), 1)
    AS opportunity_score
FROM scored
