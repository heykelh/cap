-- Chaque route sur deux fenêtres glissantes de 12 mois :
--   L12 = les 12 derniers mois publiés par le pays déclarant
--   P12 = les 12 mois précédents
-- La fenêtre s'adapte à chaque pays : Eurostat ne publie pas tous les pays à la même date.
WITH bounds AS (
  SELECT rep_country, last_month
  FROM `cap_silver.data_freshness`
),
windowed AS (
  SELECT
    r.*,
    b.last_month AS window_end,
    IF(r.month > DATE_SUB(b.last_month, INTERVAL 12 MONTH), 'L12', 'P12') AS win
  FROM `cap_silver.routes_monthly` AS r
  JOIN bounds AS b USING (rep_country)
  WHERE r.month > DATE_SUB(b.last_month, INTERVAL 24 MONTH)
),
agg AS (
  SELECT
    rep_country,
    rep_icao,
    ANY_VALUE(rep_iata) AS rep_iata,
    ANY_VALUE(rep_city) AS rep_city,
    partner_country,
    partner_icao,
    ANY_VALUE(partner_iata) AS partner_iata,
    ANY_VALUE(partner_city) AS partner_city,
    ANY_VALUE(partner_airport) AS partner_airport,
    MAX(distance_km) AS distance_km,
    MAX(window_end) AS window_end,
    SUM(IF(win = 'L12', passengers, 0)) AS pax_l12,
    SUM(IF(win = 'L12', seats, 0)) AS seats_l12,
    SUM(IF(win = 'L12', flights, 0)) AS flights_l12,
    SUM(IF(win = 'L12' AND seats > 0, passengers, 0)) AS pax_with_seats_l12,
    SUM(IF(win = 'P12', passengers, 0)) AS pax_p12,
    SUM(IF(win = 'P12', seats, 0)) AS seats_p12,
    SUM(IF(win = 'P12', flights, 0)) AS flights_p12,
    SUM(IF(win = 'P12' AND seats > 0, passengers, 0)) AS pax_with_seats_p12,
    COUNTIF(win = 'L12') AS months_l12,
    COUNTIF(win = 'L12' AND quality_flag = 'valeur_masquee') AS masked_months_l12,
    COUNTIF(win = 'L12' AND quality_flag != 'ok') AS flagged_months_l12
  FROM windowed
  GROUP BY rep_country, rep_icao, partner_country, partner_icao
)
SELECT
  *,
  ROUND(SAFE_DIVIDE(pax_with_seats_l12, seats_l12), 4) AS lf_l12,
  ROUND(SAFE_DIVIDE(pax_with_seats_p12, seats_p12), 4) AS lf_p12,
  IF(pax_p12 >= 1000, ROUND(SAFE_DIVIDE(pax_l12, pax_p12) - 1, 4), NULL) AS growth_pax,
  IF(seats_p12 >= 1000, ROUND(SAFE_DIVIDE(seats_l12, seats_p12) - 1, 4), NULL) AS growth_seats
FROM agg
