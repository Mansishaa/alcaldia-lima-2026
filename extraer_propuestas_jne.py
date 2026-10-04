#!/usr/bin/env python3
"""Descarga resúmenes oficiales de planes de gobierno para Lima Metropolitana."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "propuestas_jne.json"
API = "https://votoinformado.jne.gob.pe/api"
DOCUMENTS = "https://votoinformado.jne.gob.pe/mpesije/docs"


def request_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clean(text: str | None) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip(" .;:-")
    return value + "." if value else ""


def main() -> None:
    listing = request_json(
        f"{API}/v1/candidatos/organizaciones",
        {"dep": "14", "pro": "01", "dis": "00"},
    )
    municipal = next(item for item in listing["data"] if item["idTipoEleccion"] == 5)
    parties: dict[str, dict] = {}

    for index, party in enumerate(municipal["organizaciones"], 1):
        electoral_list = party["listas"][0]
        code = electoral_list["codigoExpediente"]
        plan = request_json(f"{API}/v1/plan-gobierno/resumen?codigoExpediente={code}")["data"]
        general = plan["datoGeneral"]
        proposals = []
        for dimension in plan.get("dimensiones") or []:
            details = dimension.get("detalle") or []
            if not details:
                continue
            proposal = details[0]
            proposals.append(
                {
                    "tema": (dimension.get("txDimension") or "Propuesta").replace("Dimensión ", ""),
                    "propuesta": clean(proposal.get("txPgObjetivo")),
                    "meta": clean(proposal.get("txPgMeta")),
                }
            )
        pdf_name = general.get("txRutaCompleto") or electoral_list.get("rutaPlanGobierno")
        parties[str(party["idOrganizacionPolitica"])] = {
            "partido": party["organizacionPolitica"],
            "expediente": code,
            "propuestas": proposals[:4],
            "plan_url": f"{DOCUMENTS}/{pdf_name}" if pdf_name else "https://votoinformado.jne.gob.pe/",
            "fuente": "Jurado Nacional de Elecciones · Voto Informado",
        }
        print(f"[{index:02d}/{len(municipal['organizaciones']):02d}] {party['organizacionPolitica']}")

    output = {
        "metadata": {
            "fecha_consulta": "2026-10-03",
            "jurisdiccion": "Lima Metropolitana",
            "nota": "Se muestra la primera propuesta de cada dimensión del resumen oficial. Las propuestas no forman parte del puntaje.",
        },
        "partidos": parties,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nArchivo generado: {OUTPUT}")


if __name__ == "__main__":
    main()
