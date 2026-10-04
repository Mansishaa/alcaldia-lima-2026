#!/usr/bin/env python3
"""Extrae perfiles de candidatos a la Alcaldía Provincial de Lima desde RTC.

Genera:
  - salida/alcaldes_lima_completo.json
  - salida/alcaldes_lima_resumen.csv
  - salida/alcaldes_lima_detalle.csv
"""

from __future__ import annotations

import csv
import html
import json
import re
import time
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


BASE_URL = "https://www.revisatucandidato.pe"
RACES_URL = f"{BASE_URL}/api/erm/races?dept=LIMA&prov=LIMA"
OUT_DIR = Path(__file__).resolve().parent / "salida"
USER_AGENT = "Mozilla/5.0 (compatible; research-export/1.0)"


def fetch_text(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
            with urlopen(req, timeout=45) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {last_error}")


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value


class CandidateIslandParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.props: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "astro-island" or self.props is not None:
            return
        values = dict(attrs)
        if "CandidateDetail" in (values.get("component-url") or ""):
            self.props = values.get("props")


def decode_astro(value: Any) -> Any:
    """Decodifica el subconjunto del serializador de Astro usado en props."""
    if isinstance(value, dict):
        return {key: decode_astro(item) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) == 2 and value[0] == 0:
            return decode_astro(value[1])
        if len(value) == 2 and value[0] == 1:
            return [decode_astro(item) for item in value[1]]
        return [decode_astro(item) for item in value]
    return value


def extract_props(page: str, url: str) -> dict[str, Any]:
    parser = CandidateIslandParser()
    parser.feed(page)
    if parser.props is None:
        raise ValueError(f"No se encontraron datos CandidateDetail en {url}")
    serialized = json.loads(html.unescape(parser.props))
    return decode_astro(serialized)


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def count_items(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(count_items(item) for item in value.values())
    return 0


def iter_fields(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        if not value:
            yield path, ""
        for key, item in value.items():
            yield from iter_fields(item, path + (str(key),))
    elif isinstance(value, list):
        if not value:
            yield path, ""
        for index, item in enumerate(value, 1):
            yield from iter_fields(item, path + (str(index),))
    else:
        yield path, value


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    races = json.loads(fetch_text(RACES_URL))
    candidates = races.get("alcProv") or []
    extracted: list[dict[str, Any]] = []

    for index, listed in enumerate(candidates, 1):
        slug = f"{slugify(listed['name'])}-{listed['dni']}"
        url = f"{BASE_URL}/candidatos/{slug}"
        print(f"[{index:02d}/{len(candidates):02d}] {listed['name']}")
        props = extract_props(fetch_text(url), url)
        record = {
            "url": url,
            "listado": listed,
            "candidato": props.get("candidate", {}),
            "detalle": props.get("initialDetail", {}),
            "proceso": props.get("proceso"),
            "companeros_formula": props.get("ticketMates", []),
            "es_finalista": props.get("isFinalist", False),
        }
        extracted.append(record)
        time.sleep(0.15)

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "metadata": {
            "fuente": BASE_URL,
            "endpoint_listado": RACES_URL,
            "alcance": "Candidatos a alcalde provincial de Lima, Lima (ERM 2026)",
            "fecha_extraccion": generated_at,
            "cantidad": len(extracted),
        },
        "candidatos": extracted,
    }
    json_path = OUT_DIR / "alcaldes_lima_completo.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_fields = [
        "id", "dni", "nombre", "edad", "genero", "partido", "partido_jne_id",
        "cargo", "estado", "jurisdiccion", "region", "foto_url", "perfil_url",
        "educacion", "trayectoria", "afiliaciones", "contratos_estado", "empresas",
        "derechos_mineros", "propiedades", "deudas", "sanciones", "experiencia_laboral",
    ]
    summary_path = OUT_DIR / "alcaldes_lima_resumen.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=summary_fields)
        writer.writeheader()
        for record in extracted:
            listed = record["listado"]
            candidate = record["candidato"]
            detail = record["detalle"]
            candidacy = (candidate.get("candidaturas") or [{}])[0]
            contracts = detail.get("contratos") or {}
            debts = detail.get("deudas") or {}
            sanctions = detail.get("sanciones") or {}
            writer.writerow({
                "id": candidate.get("id", listed.get("id")),
                "dni": candidate.get("dni", listed.get("dni")),
                "nombre": candidate.get("nombre", listed.get("name")),
                "edad": candidate.get("edad"),
                "genero": candidate.get("genero"),
                "partido": candidacy.get("partido", candidate.get("partido", listed.get("party"))),
                "partido_jne_id": candidacy.get("partidoId", candidate.get("partidoId", listed.get("partyJneId"))),
                "cargo": candidacy.get("cargo"),
                "estado": candidacy.get("estado", listed.get("status")),
                "jurisdiccion": candidacy.get("jurisdiccion"),
                "region": candidacy.get("region", candidate.get("region")),
                "foto_url": candidate.get("foto", listed.get("photoUrl")),
                "perfil_url": record["url"],
                "educacion": len(detail.get("educacion") or []),
                "trayectoria": len(detail.get("trayectoria") or []),
                "afiliaciones": len(detail.get("afiliaciones") or []),
                "contratos_estado": len(contracts.get("govContracts") or []),
                "empresas": len(contracts.get("empresas") or []),
                "derechos_mineros": len(contracts.get("miningRights") or []),
                "propiedades": len(detail.get("propiedades") or []),
                "deudas": count_items(debts),
                "sanciones": count_items(sanctions),
                "experiencia_laboral": len(detail.get("experienciaLaboral") or []),
            })

    detail_path = OUT_DIR / "alcaldes_lima_detalle.csv"
    detail_fields = ["id", "dni", "nombre", "partido", "perfil_url", "ruta", "valor"]
    with detail_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=detail_fields)
        writer.writeheader()
        for record in extracted:
            candidate = record["candidato"]
            base = {
                "id": candidate.get("id"),
                "dni": candidate.get("dni"),
                "nombre": candidate.get("nombre"),
                "partido": candidate.get("partido"),
                "perfil_url": record["url"],
            }
            for path, value in iter_fields(record):
                writer.writerow({**base, "ruta": ".".join(path), "valor": scalar(value)})

    print(f"\nExtraídos: {len(extracted)} candidatos")
    print(json_path)
    print(summary_path)
    print(detail_path)


if __name__ == "__main__":
    main()
