-- Référentiel aéroports nettoyé : un aéroport par code ICAO, avec sa position géographique.
SELECT
  COALESCE(NULLIF(icao_code, ''), ident) AS icao,
  NULLIF(iata_code, '') AS iata,
  name AS airport_name,
  NULLIF(municipality, '') AS city,
  iso_country AS country_iso2,
  type AS airport_type,
  scheduled_service = 'yes' AS has_scheduled_service,
  latitude_deg AS lat,
  longitude_deg AS lon,
  ST_GEOGPOINT(longitude_deg, latitude_deg) AS geo
FROM `cap_bronze.airports`
WHERE latitude_deg IS NOT NULL
  AND longitude_deg IS NOT NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY COALESCE(NULLIF(icao_code, ''), ident)
  ORDER BY IF(type = 'large_airport', 0, 1)
) = 1
