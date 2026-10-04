#!/usr/bin/env python3
"""Extrae las fichas de los primeros regidores que encabezan listas sin candidato a alcalde."""

from __future__ import annotations

import json
from pathlib import Path

from extraer_alcaldes_lima import extract_props, fetch_text


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "salida" / "primeros_regidores_reemplazo.json"

REPLACEMENTS = [
    {
        "slug": "rafael-bernardo-lopez-aliaga-cazorla-07845838",
        "replaces_id": 31386,
        "replaces_name": "LUIS ISAEL RUBIO IDROGO",
        "partyId": 52,
        "partyJneId": 3040,
        "partyLogoUrl": "https://sroppublico.jne.gob.pe/Consulta/Simbolo/GetSimbolo/3040",
    },
    {
        "slug": "yuri-cesar-castro-romero-40444232",
        "replaces_id": 466,
        "replaces_name": "RUBEN JOSE RAMIREZ MATEO",
        "partyId": 29,
        "partyJneId": 2218,
        "partyLogoUrl": "https://sroppublico.jne.gob.pe/Consulta/Simbolo/GetSimbolo/2218",
    },
]

TEXT_FIXES = {
    "L�PEZ": "LÓPEZ",
    "REP�BLICA": "REPÚBLICA",
    "V�LIDO": "VÁLIDO",
    "contrataci�n": "contratación",
    "CONTRATACI�N": "CONTRATACIÓN",
    "LOCUCI�N": "LOCUCIÓN",
    "INTER�S": "INTERÉS",
}


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, str):
        for broken, fixed in TEXT_FIXES.items():
            value = value.replace(broken, fixed)
    return value


def main() -> None:
    records = []
    for item in REPLACEMENTS:
        url = f"https://www.revisatucandidato.pe/candidatos/{item['slug']}"
        props = clean(extract_props(fetch_text(url), url))
        candidate = props["candidate"]
        candidacy = candidate["candidaturas"][0]
        listed = {
            "id": candidate["id"],
            "dni": candidate["dni"],
            "name": candidate["nombre"],
            "party": candidate["partido"].title(),
            "partyId": item["partyId"],
            "partyJneId": item["partyJneId"],
            "partyLogoUrl": item["partyLogoUrl"],
            "photoUrl": candidate["foto"],
            "number": 1,
            "status": candidacy["estado"],
        }
        records.append({
            "url": url,
            "listado": listed,
            "candidato": candidate,
            "detalle": props.get("initialDetail") or {},
            "proceso": props.get("proceso"),
            "companeros_formula": props.get("ticketMates", []),
            "es_finalista": props.get("isFinalist", False),
            "rol_lista": "PRIMER REGIDOR QUE ENCABEZA LISTA SIN CANDIDATO A ALCALDE",
            "sustituye_id": item["replaces_id"],
            "sustituye_nombre": item["replaces_name"],
        })
        print(f"Extraído: {candidate['nombre']}")

    OUTPUT.write_text(json.dumps({"candidatos": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
