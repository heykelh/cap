"""Contrôle : les routes CDG absentes du radar sont-elles des données confidentielles ?

Usage (après une ingestion France en --local-only) :
  python ingestion/check_confidential.py
"""
import pandas as pd

df = pd.read_parquet("data/bronze/eurostat_routes.parquet")
cdg = df[df["rep_icao"] == "LFPG"]

print("Lignes CDG :", len(cdg))
print("dont valeur vide (confidentielle ou absente) :", int(cdg["value"].isna().sum()))
print()
print("Statuts rencontrés sur les valeurs vides :")
print(cdg[cdg["value"].isna()][["obs_flag", "conf_status"]].value_counts(dropna=False).head(10))
print()

watch = ["OMDB", "KATL", "FACT", "KDEN", "KJFK"]
sub = cdg[cdg["partner_icao"].isin(watch)]
summary = (
    sub.assign(vide=sub["value"].isna())
    .groupby(["partner_icao", "measure"])
    .agg(mois=("period", "nunique"), mois_vides=("vide", "sum"), derniere=("period", "max"))
)
print("Routes témoins (KJFK = contrôle, toujours publiée) :")
print(summary)
