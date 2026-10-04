#!/usr/bin/env python3
"""Genera un catálogo HTML visual de candidatos a la Alcaldía de Lima."""

from __future__ import annotations

import io
import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "salida" / "alcaldes_lima_completo.json"
REPLACEMENTS = ROOT / "salida" / "primeros_regidores_reemplazo.json"
RESEARCH = ROOT / "investigacion_adicional.json"
AUDIT = ROOT / "auditoria_gestion.json"
PROPOSALS = ROOT / "propuestas_jne.json"
SITE = ROOT / "sitio_alcaldes_lima"
DIST = SITE / "dist"
ASSETS = DIST / "assets"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def download_webp(url: str | None, destination: Path, square: bool = False) -> bool:
    if not url:
        return False
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*"})
        with urlopen(request, timeout=30) as response:
            raw = response.read()
        with Image.open(io.BytesIO(raw)) as image:
            image = image.convert("RGBA" if image.mode in {"RGBA", "LA"} else "RGB")
            if square:
                size = max(image.size)
                canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
                canvas.alpha_composite(image.convert("RGBA"), ((size - image.width) // 2, (size - image.height) // 2))
                image = canvas
            image.thumbnail((720, 900) if not square else (320, 320), Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, "WEBP", quality=86, method=6)
        return True
    except Exception as exc:
        print(f"Advertencia: no se pudo descargar {url}: {exc}")
        return False


def score_candidate(record: dict, research: dict | None = None) -> dict:
    """Puntaje documental explícito; no representa intención ni recomendación de voto."""
    detail = record.get("detalle") or {}
    indicators = detail.get("indicadores") or {}
    driving = (detail.get("deudas") or {}).get("drivingRecord") or {}
    status = (record.get("listado") or {}).get("status")
    supplement = (research or {}).get("suplemento") or {}

    education_count = max(len(detail.get("educacion") or []), int(supplement.get("educacion") or 0))
    political_count = max(len(detail.get("trayectoria") or []), int(supplement.get("trayectoria") or 0))
    professional_count = max(len(detail.get("experienciaLaboral") or []), int(supplement.get("experienciaLaboral") or 0))
    education = round(min(education_count, 3) / 3 * 20)
    political = round(min(political_count, 5) / 5 * 20)
    professional = round(min(professional_count, 5) / 5 * 20)
    candidacy = {"INSCRITO": 10, "ADMITIDO": 7}.get(status, 0)

    sanctions = min(max(int(indicators.get("sanciones") or 0), int(supplement.get("sanciones") or 0)), 3)
    debts = min(max(int(indicators.get("deudas") or 0), int(supplement.get("deudas") or 0)), 3)
    serious = min(int(driving.get("seriousViolations") or 0), 2)
    very_serious = min(int(driving.get("verySeriousViolations") or 0), 2)
    alerts = max(0, 25 - sanctions * 6 - debts * 4 - serious - very_serious * 2)

    expected = ["educacion", "trayectoria", "contratos", "propiedades", "deudas", "sanciones", "experienciaLaboral"]
    completeness = round(sum(key in detail for key in expected) / len(expected) * 5)
    total = education + political + professional + candidacy + alerts + completeness
    tier = "S" if total >= 85 else "A" if total >= 70 else "B" if total >= 55 else "C" if total >= 40 else "D"
    result = {
        "total": total,
        "tier": tier,
        "componentes": {
            "Formación declarada": education,
            "Trayectoria política": political,
            "Experiencia laboral": professional,
            "Estado de candidatura": candidacy,
            "Alertas documentales": alerts,
            "Completitud del registro": completeness,
        },
        "maximos": {
            "Formación declarada": 20,
            "Trayectoria política": 20,
            "Experiencia laboral": 20,
            "Estado de candidatura": 10,
            "Alertas documentales": 25,
            "Completitud del registro": 5,
        },
    }
    return result


def score_audit(audit: dict, maxima: dict[str, int]) -> dict:
    values = audit["componentes"]
    components = dict(zip(maxima.keys(), values, strict=True))
    total = sum(values)
    tier = "S" if total >= 85 else "A" if total >= 70 else "B" if total >= 55 else "C" if total >= 40 else "D"
    return {
        "total": total,
        "tier": tier,
        "componentes": components,
        "maximos": maxima,
        "confianza": audit.get("confianza", "Baja"),
        "resumen_auditoria": audit.get("resumen", ""),
        "fuentes_auditoria": audit.get("fuentes", []),
        "cambio": 0,
    }


def html_template(data_json: str, extracted_date: str) -> str:
    return r'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Una guía sencilla para conocer a los candidatos a la Alcaldía de Lima, sus propuestas, experiencia y alertas.">
  <title>¿Quiénes quieren gobernar Lima? · Elecciones 2026</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,700&display=swap" rel="stylesheet">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%2380192c'/%3E%3Cpath d='M17 16h30v8H17zm4 13h22v20H21z' fill='white'/%3E%3Cpath d='m27 37 4 4 8-10' fill='none' stroke='%2380192c' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
  <style>
    :root{--ink:#18202b;--muted:#66717f;--paper:#f4f6f8;--card:#fff;--brand:#80192c;--brand-dark:#520b19;--gold:#d29a2e;--line:#dfe3e8;--shadow:0 18px 55px rgba(24,32,43,.12);color-scheme:light}
    *{box-sizing:border-box}html{scroll-behavior:smooth;max-width:100%;overflow-x:hidden}body{margin:0;max-width:100%;overflow-x:hidden;background:var(--paper);color:var(--ink);font:400 1rem/1.55 "DM Sans",sans-serif}button,input,select{font:inherit}button{cursor:pointer}a{color:inherit}
    .topbar{position:sticky;top:0;z-index:20;background:rgba(82,11,25,.96);backdrop-filter:blur(14px);color:#fff;border-bottom:1px solid rgba(255,255,255,.14)}
    .topbar-inner{max-width:1440px;margin:auto;padding:.8rem clamp(1rem,3vw,2.5rem);display:flex;align-items:center;justify-content:space-between;gap:1rem}.brand{display:flex;align-items:center;gap:.7rem;font-weight:700}.mark{display:grid;place-items:center;width:2rem;height:2rem;border-radius:.55rem;background:#fff;color:var(--brand);font-size:.9rem}.stamp{font-size:.8rem;color:#efc9d1}
    main{max-width:1440px;margin:auto;padding:clamp(1rem,2.5vw,2.2rem)}
    .intro{margin-bottom:1rem}.intro>*{min-width:0}.eyebrow{margin:0 0 .35rem;color:var(--brand);font-size:.76rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase}.intro h1{font:700 clamp(2rem,4vw,3.35rem)/1 "Fraunces",serif;letter-spacing:-.035em;margin:0;max-width:950px;overflow-wrap:anywhere}.intro-copy{color:var(--muted);max-width:850px;margin:.55rem 0 0}.summary{display:none}
    .controls{position:sticky;top:57px;z-index:15;display:grid;grid-template-columns:minmax(220px,1fr) minmax(180px,.55fr) auto;gap:.8rem;align-items:center;background:rgba(244,246,248,.94);backdrop-filter:blur(16px);padding:.85rem 0;border-block:1px solid var(--line);margin-bottom:1.2rem}.controls>*{min-width:0}.field{position:relative}.field svg{position:absolute;left:.9rem;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none}.control{width:100%;min-width:0;max-width:100%;min-height:46px;border:1px solid var(--line);border-radius:.75rem;background:#fff;color:var(--ink);padding:.7rem .9rem}.search{padding-left:2.8rem}.control:focus{outline:3px solid rgba(128,25,44,.16);border-color:var(--brand)}.count{white-space:nowrap;color:var(--muted);font-size:.9rem;text-align:right}.count strong{color:var(--ink)}
    .methodology{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1rem;align-items:center;margin:0 0 1.2rem;padding:.8rem 1rem;border:1px solid #e4c56e;border-left:5px solid var(--gold);border-radius:.9rem;background:#fffaf0}.methodology strong{display:block;color:#67480a}.methodology p{margin:.1rem 0 0;color:#705d38;font-size:.84rem}.methodology details{position:relative}.methodology summary{list-style:none;white-space:nowrap;border:1px solid #d9b554;border-radius:.65rem;padding:.48rem .7rem;background:#fff;font-weight:700;color:#67480a;cursor:pointer}.methodology summary::-webkit-details-marker{display:none}.methodology-panel{position:absolute;right:0;top:calc(100% + .5rem);z-index:18;width:min(620px,calc(100vw - 2rem));padding:1rem;border:1px solid #e4c56e;border-radius:.8rem;background:#fff;box-shadow:var(--shadow)}.methodology-panel h3{margin:0 0 .5rem;font:700 1.2rem "Fraunces",serif}.methodology-panel ul{margin:.5rem 0;padding-left:1.2rem}.methodology-panel li{margin:.25rem 0;font-size:.86rem;color:var(--muted)}
    .polls{margin:0 0 1.2rem;padding:1rem 1.1rem;border:1px solid #cbd7e3;border-left:5px solid #376d99;border-radius:.9rem;background:#f7fafc}.polls-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}.polls h2{margin:0;font:700 1.35rem/1.15 "Fraunces",serif;color:var(--brand-dark)}.polls h3{margin:1rem 0 .55rem;font-size:1rem;color:#263849}.polls p{margin:.35rem 0 0;color:#526474;font-size:.9rem}.poll-badge{flex:0 0 auto;border-radius:999px;background:#e5f0f8;color:#245f91;padding:.35rem .65rem;font-size:.75rem;font-weight:800}.poll-lead{margin-top:.85rem!important;padding:.75rem .85rem;border-radius:.7rem;background:#fff;border:1px solid #d8e2eb;color:#263849!important}.poll-bars{display:grid;gap:.42rem;margin-top:.65rem}.poll-bar{display:grid;grid-template-columns:minmax(145px,220px) 1fr 3rem;gap:.6rem;align-items:center;font-size:.82rem}.poll-track{height:.72rem;border-radius:999px;background:#e2e8ee;overflow:hidden}.poll-fill{display:block;height:100%;border-radius:999px;background:#80192c}.poll-value{text-align:right;font-weight:800}.poll-table-wrap{overflow-x:auto;border:1px solid #d8e2eb;border-radius:.75rem;background:#fff}.poll-table{width:100%;min-width:760px;border-collapse:collapse}.poll-table th,.poll-table td{padding:.65rem .7rem;border-bottom:1px solid #e2e8ee;text-align:left;font-size:.8rem;vertical-align:top}.poll-table th{background:#eef4f8;color:#263849}.poll-table tr:last-child td{border-bottom:0}.poll-table strong{color:var(--brand-dark)}.polls details{margin-top:.8rem}.polls summary{cursor:pointer;color:#245f91;font-weight:700}.polls ul{margin:.55rem 0 .2rem;padding-left:1.2rem;color:#526474;font-size:.86rem}.polls a{color:#245f91;font-weight:700}
    .spotlight{margin:0 0 1.2rem;padding:1.1rem;border:1px solid #d7c9eb;border-radius:1rem;background:linear-gradient(145deg,#fbf9ff,#f4f0fb)}.spotlight-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:.9rem}.spotlight h2{margin:0;font:700 1.45rem/1.15 "Fraunces",serif;color:#41266e}.spotlight-head p{margin:.3rem 0 0;max-width:780px;color:#655b72;font-size:.86rem}.spotlight-badge{flex:0 0 auto;border-radius:999px;background:#7046b8;color:#fff;padding:.35rem .65rem;font-size:.72rem;font-weight:800}.spotlight-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.75rem}.spot-card{display:flex;flex-direction:column;min-width:0;padding:.9rem;border:1px solid #dfd6ed;border-top:4px solid #7046b8;border-radius:.85rem;background:#fff;box-shadow:0 7px 24px rgba(63,38,104,.07)}.spot-person{display:grid;grid-template-columns:58px minmax(0,1fr);gap:.7rem;align-items:center}.spot-person img{width:58px;height:58px;border-radius:.7rem;object-fit:cover;object-position:center top;background:#ddd}.spot-person h3{margin:0;font:700 1rem/1.1 "Fraunces",serif;color:#2e2042}.spot-meta{display:block;margin-top:.25rem;color:#746985;font-size:.69rem;font-weight:700}.spot-line{margin:.7rem 0;padding:.65rem;border-radius:.65rem;background:#f4f0fb;color:#402a61;font-size:.79rem;font-weight:700;line-height:1.4}.spot-item{margin:.5rem 0 0}.spot-item strong{display:block;margin-bottom:.12rem;color:#263849;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}.spot-item p{margin:0;color:#52606d;font-size:.76rem;line-height:1.42}.spot-item.caution strong{color:#9b3d2d}.spot-card .view{margin-top:auto;padding-top:.58rem;padding-bottom:.58rem}
    .spot-item p{font-size:.8rem;line-height:1.48}
    .status-tabs{display:flex;gap:.45rem;flex-wrap:wrap;margin:0 0 1.2rem}.status-tab{border:1px solid var(--line);background:#fff;padding:.48rem .75rem;border-radius:999px;color:var(--muted);font-size:.85rem;font-weight:600}.status-tab[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:#fff}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(245px,1fr));gap:1rem}.card{position:relative;display:flex;flex-direction:column;min-width:0;background:var(--card);border:1px solid var(--line);border-radius:1rem;overflow:hidden;box-shadow:0 1px 0 rgba(24,32,43,.03);transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}.card:hover{transform:translateY(-3px);box-shadow:var(--shadow);border-color:#c8ccd3}.portrait-wrap{position:relative;aspect-ratio:4/3;background:linear-gradient(145deg,#e9edf1,#d6dce3);overflow:hidden}.portrait{width:100%;height:100%;object-fit:cover;object-position:center 20%;display:block}.party-logo{position:absolute;right:.8rem;bottom:.8rem;width:3.4rem;height:3.4rem;object-fit:contain;background:#fff;border:1px solid var(--line);border-radius:.8rem;padding:.35rem;box-shadow:0 5px 16px rgba(0,0,0,.15)}.status{position:absolute;top:.75rem;left:.75rem;padding:.35rem .6rem;border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;background:#fff;color:var(--ink);box-shadow:0 4px 12px rgba(0,0,0,.12)}.status.inscrito{color:#12623a}.status.admitido{color:#145d83}.status.renuncia,.status.improcedente{color:#9a1f2b}.card-body{display:flex;flex:1;flex-direction:column;padding:1rem}.party{font-size:.76rem;font-weight:700;color:var(--brand);text-transform:uppercase;line-height:1.3;min-height:2em}.card h2{font:700 1.28rem/1.15 "Fraunces",serif;margin:.45rem 0}.meta{display:flex;gap:.7rem;flex-wrap:wrap;color:var(--muted);font-size:.82rem;margin-top:auto;padding-top:.6rem}.view{width:100%;margin-top:.9rem;border:0;border-radius:.7rem;background:var(--ink);color:#fff;padding:.68rem;font-weight:700}.view:hover{background:var(--brand)}
    .tier-board{display:grid;gap:.9rem}.tier-row{display:grid;grid-template-columns:150px minmax(0,1fr);min-height:190px;border:1px solid var(--line);border-radius:1rem;overflow:hidden;background:#fff;box-shadow:0 1px 0 rgba(24,32,43,.04)}.tier-label{display:flex;flex-direction:column;justify-content:center;align-items:center;padding:1rem;text-align:center;color:#17202b}.tier-letter{font:700 4.3rem/.9 "Fraunces",serif}.tier-label strong{margin-top:.65rem;font-size:.86rem}.tier-label span{margin-top:.2rem;font-size:.72rem;opacity:.75}.tier-s .tier-label{background:#efb236}.tier-a .tier-label{background:#f1d06f}.tier-b .tier-label{background:#a9d5c2}.tier-c .tier-label{background:#a9c7e6}.tier-d .tier-label{background:#c8cdd4}.tier-cards{display:flex;gap:.75rem;align-items:stretch;overflow-x:auto;padding:.8rem;scrollbar-color:#aab2bd transparent}.tier-card{position:relative;flex:0 0 176px;display:flex;flex-direction:column;min-width:0;border:1px solid var(--line);border-radius:.8rem;overflow:hidden;background:#fff;transition:transform .16s ease,box-shadow .16s ease}.tier-card:hover{transform:translateY(-2px);box-shadow:0 10px 28px rgba(24,32,43,.15)}.tier-photo{position:relative;height:112px;background:#e8ebef;overflow:hidden}.tier-photo .portrait{object-position:center 20%}.tier-photo .party-logo{right:.5rem;bottom:.5rem;width:2.45rem;height:2.45rem;border-radius:.55rem;padding:.22rem}.tier-score{position:absolute;top:.5rem;left:.5rem;display:grid;place-items:center;min-width:2.45rem;height:2.45rem;padding:0 .35rem;border-radius:50%;background:var(--ink);color:#fff;font:700 1rem "Fraunces",serif;border:2px solid #fff;box-shadow:0 3px 10px rgba(0,0,0,.2)}.score-change{position:absolute;top:.5rem;right:.5rem;padding:.22rem .42rem;border-radius:999px;background:#fff;color:#12623a;border:1px solid #b9dfca;font-size:.62rem;font-weight:800;box-shadow:0 2px 8px rgba(0,0,0,.12)}.tier-card-body{display:flex;flex:1;flex-direction:column;padding:.7rem}.tier-card .party{font-size:.63rem;min-height:0}.tier-card h2{font:700 .94rem/1.15 "Fraunces",serif;margin:.35rem 0 .45rem}.tier-card .status-line{margin-top:auto;font-size:.68rem;font-weight:700;color:var(--muted)}.role-note{display:block;margin-top:.25rem;color:#245f91;font-size:.62rem;font-weight:800;line-height:1.25}.research-count{display:inline-flex;margin-top:.3rem;color:var(--brand);font-size:.66rem;font-weight:700}.tier-card .view{margin-top:.55rem;padding:.48rem;font-size:.76rem}
    .tier-card.follow-up{border:2px solid #7046b8;box-shadow:0 0 0 3px rgba(112,70,184,.1)}.follow-marker{position:absolute;z-index:2;top:.48rem;right:.48rem;padding:.25rem .45rem;border-radius:999px;background:#7046b8;color:#fff;font-size:.59rem;font-weight:800;letter-spacing:.02em;box-shadow:0 3px 10px rgba(34,19,61,.28)}.follow-note{display:inline-flex;align-items:center;gap:.28rem;margin-top:.35rem;color:#5d379c;font-size:.66rem;font-weight:800}.follow-note::before{content:'★'}
    .empty{display:none;text-align:center;padding:4rem 1rem;color:var(--muted)}
    .external-help{display:none}
    .profile-hero{position:sticky;top:0;z-index:4;display:grid;grid-template-columns:92px minmax(0,1fr) auto;gap:1rem;align-items:center;padding:1rem 1.2rem;background:linear-gradient(130deg,var(--brand-dark),#8d2438);color:#fff}.profile-portrait{width:92px;height:92px;border-radius:1rem;object-fit:cover;object-position:center top;background:#ddd;border:2px solid rgba(255,255,255,.35)}.profile-title{min-width:0}.profile-title h2{margin:0;font:700 clamp(1.35rem,3vw,2rem)/1.05 "Fraunces",serif;overflow-wrap:anywhere}.profile-title p{margin:.32rem 0 0;color:#f0cbd3;font-size:.85rem;overflow-wrap:anywhere}.profile-score{display:grid;place-items:center;width:74px;height:74px;border-radius:50%;background:#fff;color:var(--brand-dark);border:5px solid #efc46d;font:700 1.45rem "Fraunces",serif}.profile-score small{display:block;font:700 .58rem "DM Sans",sans-serif;text-align:center}.profile-hero .close{position:absolute;right:.55rem;top:.45rem;width:2rem;height:2rem;font-size:1rem}.profile-shell{min-width:0;overflow-x:hidden;padding:1rem 1.2rem 1.3rem}.quick-facts{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.55rem;margin-bottom:1rem}.quick-fact{min-width:0;padding:.7rem;border:1px solid var(--line);border-radius:.75rem;background:#fff;overflow:hidden}.quick-fact strong{display:block;font:700 1.05rem "Fraunces",serif;color:var(--brand-dark)}.quick-fact span{display:block;margin-top:.1rem;color:var(--muted);font-size:.68rem;line-height:1.25;overflow-wrap:anywhere}.profile-tabs{display:flex;gap:.4rem;overflow-x:auto;padding:.15rem 0 .7rem;border-bottom:1px solid var(--line)}.profile-tab{white-space:nowrap;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--muted);padding:.48rem .75rem;font-size:.8rem;font-weight:700}.profile-tab[aria-selected="true"]{background:var(--brand);border-color:var(--brand);color:#fff}.profile-panel{display:none;padding-top:1rem}.profile-panel.active{display:block}.dashboard{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr);gap:1rem}.verdict{padding:1rem;border-radius:.9rem;background:#f8f1f3;border-left:5px solid var(--brand)}.verdict h3,.score-panel h3,.panel-title{margin:0 0 .55rem;font:700 1.18rem "Fraunces",serif;color:var(--brand-dark)}.verdict p{margin:.25rem 0;color:#394655}.score-panel{padding:1rem;border:1px solid var(--line);border-radius:.9rem;background:#fff}.score-row{display:grid;grid-template-columns:minmax(130px,1fr) 2fr auto;gap:.55rem;align-items:center;margin:.55rem 0;font-size:.76rem}.score-track{height:.55rem;background:#e4e8ed;border-radius:999px;overflow:hidden}.score-fill{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--brand),#d29a2e)}.score-number{font-weight:800}.source-grid,.timeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.source-card,.timeline-card,.signal-card{padding:.8rem;border:1px solid var(--line);border-radius:.75rem;background:#fff}.source-card strong,.timeline-card strong{display:block;color:var(--brand-dark);font-size:.88rem}.source-card a{display:inline-block;margin-top:.4rem;color:#245f91;font-size:.78rem;font-weight:700}.timeline-card p{margin:.22rem 0;color:#526474;font-size:.78rem}.timeline-card span{font-size:.7rem;color:var(--muted)}.signal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem}.signal-card strong{display:block;font:700 1.3rem "Fraunces",serif;color:var(--brand-dark)}.signal-card span{color:var(--muted);font-size:.75rem}.signal-note{margin:.8rem 0 0;padding:.75rem;border-radius:.7rem;background:#fff8e8;color:#6b531b;font-size:.8rem}.raw-group{margin:.55rem 0;border:1px solid var(--line);border-radius:.75rem;background:#fff;overflow:hidden}.raw-group>summary{padding:.72rem .85rem;cursor:pointer;font-weight:700;color:var(--brand-dark)}.raw-group>div{padding:.2rem .75rem .8rem}.empty-brief{padding:1rem;border:1px dashed #c8d0d8;border-radius:.75rem;color:var(--muted);font-size:.82rem;text-align:center}
    .proposal-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:.8rem;padding:.85rem 1rem;border-radius:.85rem;background:#eef7f2;border-left:5px solid #318565}.proposal-intro h3{margin:0;font:700 1.15rem "Fraunces",serif;color:#165b45}.proposal-intro p{margin:.2rem 0 0;color:#48665c;font-size:.8rem}.proposal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}.proposal-card{padding:.9rem;border:1px solid #cfe1d9;border-radius:.8rem;background:#fff}.proposal-topic{display:inline-block;margin-bottom:.35rem;padding:.2rem .45rem;border-radius:999px;background:#dff1e8;color:#176246;font-size:.67rem;font-weight:800;text-transform:uppercase}.proposal-card h4{margin:.15rem 0;font-size:.92rem;line-height:1.35;color:#263b34}.proposal-card details{margin-top:.5rem}.proposal-card summary{cursor:pointer;color:#557069;font-size:.72rem;font-weight:700}.proposal-card p{margin:.35rem 0 0;color:#5b6c66;font-size:.73rem}.plan-link{display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;border-radius:.65rem;background:#176246;color:#fff;padding:.55rem .7rem;text-decoration:none;font-size:.75rem;font-weight:800}.no-proposals{padding:1rem;border:1px dashed #bdc7c2;border-radius:.75rem;color:var(--muted);text-align:center}
    dialog{width:min(960px,calc(100% - 2rem));max-height:calc(100dvh - 2rem);padding:0;border:0;border-radius:1.2rem;box-shadow:0 25px 90px rgba(0,0,0,.35);color:var(--ink)}dialog::backdrop{background:rgba(16,21,29,.72);backdrop-filter:blur(5px)}.modal-head{position:sticky;top:0;z-index:4;display:grid;grid-template-columns:86px 1fr auto;gap:1rem;align-items:center;background:var(--brand-dark);color:#fff;padding:1rem 1.2rem}.modal-photo{width:86px;height:86px;border-radius:.85rem;object-fit:cover;object-position:center top;background:#ddd}.modal-head h2{font:700 clamp(1.4rem,4vw,2rem)/1.05 "Fraunces",serif;margin:0}.modal-party{margin:.35rem 0 0;color:#f0cbd3;font-size:.88rem}.close{align-self:start;border:1px solid rgba(255,255,255,.25);background:transparent;color:#fff;width:2.5rem;height:2.5rem;border-radius:50%;font-size:1.4rem}.close:hover{background:#fff;color:var(--brand)}.modal-body{padding:1.2rem}.profile-intro{display:flex;gap:.55rem;flex-wrap:wrap;margin-bottom:1rem}.pill{background:var(--paper);border:1px solid var(--line);border-radius:999px;padding:.38rem .65rem;font-size:.83rem}.pill.changed{background:#edf8f2;border-color:#b9dfca;color:#12623a;font-weight:700}.section{border-top:1px solid var(--line);padding:1.1rem 0}.section:first-child{border-top:0}.section h3{font:700 1.35rem/1.2 "Fraunces",serif;color:var(--brand-dark);margin:0 0 .8rem}.section h4{margin:1rem 0 .45rem;color:var(--brand);font-size:1rem}.research-box{padding:1rem;border:1px solid #cad6e2;border-left:5px solid #376d99;border-radius:.85rem;background:#f5f9fc}.research-box>p{margin:.15rem 0 .8rem}.finding{padding:.8rem 0;border-top:1px solid #d8e2eb}.finding h4{margin:0 0 .25rem}.finding p{margin:.2rem 0;font-size:.88rem}.finding a{color:#245f91;font-weight:700}.impact{color:var(--muted);font-size:.78rem!important}.records{display:grid;gap:.75rem}.record{border:1px solid var(--line);border-radius:.75rem;overflow:hidden;background:#fff}.kv{width:100%;border-collapse:collapse}.kv th,.kv td{text-align:left;vertical-align:top;padding:.58rem .7rem;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.kv tr:last-child th,.kv tr:last-child td{border-bottom:0}.kv th{width:31%;background:#f8f1f3;color:var(--brand-dark);font-size:.8rem}.kv td{font-size:.88rem}.no-data{color:var(--muted);font-style:italic;margin:.25rem 0}.nested{padding:.7rem}.source-note{font-size:.78rem;color:var(--muted);margin-top:1rem}.source-note a{color:var(--brand)}
    footer{max-width:1440px;margin:2rem auto 0;padding:1.5rem clamp(1rem,3vw,2.5rem);border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}
    @media(max-width:800px){.controls{grid-template-columns:1fr 1fr;top:57px}.count{grid-column:1/-1;text-align:left}.modal-head{grid-template-columns:64px 1fr auto}.modal-photo{width:64px;height:64px}.methodology{grid-template-columns:1fr}.methodology details{justify-self:start}.methodology-panel{left:0;right:auto}.tier-row{grid-template-columns:105px minmax(0,1fr)}.tier-letter{font-size:3.5rem}.quick-facts{grid-template-columns:repeat(3,minmax(0,1fr))}.dashboard{grid-template-columns:1fr}}
    @media(max-width:560px){main{padding:1rem}.stamp{display:none}.intro h1{font-size:2rem}.intro-copy{font-size:.9rem;line-height:1.45}.controls{position:static;grid-template-columns:minmax(0,1fr);padding:.7rem 0;margin-bottom:.7rem}.count{grid-column:auto}.status-tabs{margin-bottom:.8rem}.tier-row{display:block;min-height:0}.tier-label{align-items:flex-start;text-align:left;padding:.55rem .8rem}.tier-letter{font-size:2.2rem}.tier-label strong{margin:.1rem 0 0}.tier-label span{margin:0}.tier-cards{padding:.65rem}.tier-card{flex-basis:158px}.methodology-panel{position:fixed;inset:auto 1rem 1rem 1rem;width:auto;max-height:70vh;overflow:auto}.modal-head{grid-template-columns:52px minmax(0,1fr) auto;padding:.8rem}.modal-photo{width:52px;height:52px}.modal-body{padding:.85rem}.kv th{width:40%}.profile-hero{grid-template-columns:64px minmax(0,1fr) 54px;padding:.8rem}.profile-portrait{width:64px;height:64px}.profile-score{width:54px;height:54px;border-width:3px;font-size:1rem}.profile-shell{padding:.8rem}.quick-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.source-grid,.timeline{grid-template-columns:1fr}.signal-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.score-row{grid-template-columns:1fr auto}.score-track{grid-column:1/-1;grid-row:2}.polls-head{display:block}.poll-badge{display:inline-block;margin-top:.5rem}}
    @media(max-width:560px){dialog{left:6px!important;right:auto!important;width:calc(100vw - 12px)!important;max-width:calc(100vw - 12px)!important;min-width:0!important;margin-inline:0;overflow-x:hidden}#modal-content{width:100%;min-width:0;overflow:hidden}.profile-title h2{font-size:1.02rem}.profile-title p{font-size:.7rem}.profile-hero{width:100%;max-width:100%;min-width:0;grid-template-columns:56px minmax(0,1fr);padding-right:2.5rem}.profile-portrait{width:56px;height:56px}.profile-score{display:none}.profile-shell,.quick-facts,.profile-tabs{width:100%;max-width:100%;min-width:0}}
    @media(max-width:560px){.proposal-grid{grid-template-columns:1fr}.proposal-intro,.spotlight-head{display:block}.plan-link{margin-top:.65rem;width:100%}.spotlight{padding:.85rem}.spotlight-badge{display:inline-block;margin-top:.65rem}.spotlight-grid{grid-template-columns:1fr}}
    @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
  </style>
</head>
<body>
  <header class="topbar"><div class="topbar-inner"><div class="brand"><span class="mark">LM</span><span>Alcaldía de Lima 2026</span></div><span class="stamp">Guía ciudadana · v8 · 03/10/2026</span></div></header>
  <main>
    <section class="intro" aria-labelledby="page-title">
      <div><p class="eyebrow">Elecciones municipales 2026</p><h1 id="page-title">¿Quiénes quieren gobernar Lima?</h1><p class="intro-copy">Mira rápido quién es quién, qué ha hecho, qué propone y qué cosas debería explicar. Si una lista se quedó sin candidato a alcalde, mostramos al primer regidor que la encabeza. Esta página no te dice por quién votar.</p></div>
      <div class="summary" id="summary" aria-hidden="true"></div>
    </section>
    <section class="controls" aria-label="Controles de búsqueda">
      <label class="field"><span class="sr-only"></span><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg><input id="search" class="control search" type="search" placeholder="Buscar candidato o partido…" autocomplete="off" aria-label="Buscar candidato o partido"></label>
      <select id="party" class="control" aria-label="Filtrar por organización política"><option value="">Todos los partidos</option></select>
      <div class="count" aria-live="polite"><strong id="visible-count">0</strong> perfiles encontrados</div>
    </section>
    <div class="status-tabs" id="status-tabs" aria-label="Filtrar por estado"></div>
    <aside class="methodology">
      <div><strong>¿Qué significa el puntaje?</strong><p>Comparamos experiencia, resultados, manejo del dinero público, problemas comprobados y transparencia. Una denuncia no se trata como una condena.</p></div>
      <details><summary>Ver cómo puntuamos</summary><div class="methodology-panel"><h3>Así sale la nota · 100 puntos</h3><ul><li>Experiencia para el cargo: hasta 20 puntos.</li><li>Resultados que se pueden comprobar: hasta 25 puntos.</li><li>Cómo manejó el dinero y las contrataciones: hasta 20 puntos.</li><li>Problemas legales o incumplimientos comprobados: hasta 20 puntos.</li><li>Qué tan clara y abierta fue su gestión: hasta 15 puntos.</li><li>Si casi no hay información para comprobar su trabajo, lo decimos y ponemos una nota prudente.</li><li>Las investigaciones se muestran como asuntos pendientes, no como prueba de culpabilidad.</li></ul><p>S: 85–100 · A: 70–84 · B: 55–69 · C: 40–54 · D: 0–39. Puedes revisar las fuentes dentro de cada ficha.</p></div></details>
    </aside>
    <section class="polls" aria-labelledby="polls-title">
      <div class="polls-head"><div><h2 id="polls-title">Encuestas anteriores a la veda</h2><p>Archivo histórico de estudios publicados antes del 28 de septiembre de 2026. No es una medición actual ni modifica el puntaje de gestión.</p></div><span class="poll-badge">Datos históricos</span></div>
      <p class="poll-lead"><strong>Lectura general:</strong> Renovación Popular, representada en estas mediciones por Rafael López Aliaga como primer regidor, encabezaba los estudios seleccionados. Sin embargo, el IEP encontró un empate estadístico entre López Aliaga y Carlos Bruce; por ello no todas las diferencias deben leerse como una ventaja concluyente.</p>
      <details class="poll-results"><summary>Ver gráficos, comparación y fichas técnicas</summary>
      <h3>Evolución histórica en las mediciones de Ipsos</h3>
      <div class="poll-table-wrap"><table class="poll-table"><thead><tr><th>Medición</th><th>Primer lugar</th><th>Segundo lugar</th><th>Tercero</th><th>Contexto</th></tr></thead><tbody>
        <tr><td><strong>Mayo</strong><br>campo 16–17 may.</td><td>Carlos Bruce<br>13%</td><td>Daniel Urresti<br>12%</td><td>Hernán Sifuentes<br>10%</td><td>466 entrevistas; error ±4,5%. Allison y Paredes registraban 9% cada uno.</td></tr>
        <tr><td><strong>Julio</strong></td><td>Carlos Bruce<br>14%</td><td>Samuel Daza<br>10%</td><td>Luis Rubio / RP<br>10%</td><td>Rubio todavía encabezaba la lista de Renovación Popular; Allison tenía 9%.</td></tr>
        <tr><td><strong>Agosto</strong><br>campo 5–6 ago.</td><td>López Aliaga / RP<br>21%</td><td>Carlos Bruce<br>13%</td><td>Francis Allison<br>9%</td><td>Primer estudio de esta serie después de la renuncia de Rubio; Urresti tenía 7%.</td></tr>
        <tr><td><strong>Septiembre</strong><br>campo 24–25 sep.</td><td>López Aliaga / RP<br>25%</td><td>Carlos Bruce<br>14%</td><td>Francis Allison<br>13%</td><td>Última encuesta publicable de Ipsos; 803 entrevistas y error ±3,46%.</td></tr>
      </tbody></table></div>
      <p>La secuencia muestra un cambio de liderazgo: Bruce aparecía primero en mayo y julio; Renovación Popular pasó al primer lugar desde agosto, después de que López Aliaga sustituyera a Rubio como figura visible de la lista. El cambio de nombres y candidaturas limita la comparación directa.</p>
      <h3>Última encuesta publicable de Ipsos · campo 24–25 sep.</h3>
      <div class="poll-bars" aria-label="Intención de voto Ipsos septiembre 2026">
        <div class="poll-bar"><span>Rafael López Aliaga / RP</span><span class="poll-track"><span class="poll-fill" style="width:100%"></span></span><span class="poll-value">25%</span></div>
        <div class="poll-bar"><span>Carlos Bruce</span><span class="poll-track"><span class="poll-fill" style="width:56%"></span></span><span class="poll-value">14%</span></div>
        <div class="poll-bar"><span>Francis Allison</span><span class="poll-track"><span class="poll-fill" style="width:52%"></span></span><span class="poll-value">13%</span></div>
        <div class="poll-bar"><span>Daniel Urresti</span><span class="poll-track"><span class="poll-fill" style="width:32%"></span></span><span class="poll-value">8%</span></div>
        <div class="poll-bar"><span>Samuel Daza</span><span class="poll-track"><span class="poll-fill" style="width:24%"></span></span><span class="poll-value">6%</span></div>
      </div>
      <p>Ipsos entrevistó presencialmente a 803 personas en la provincia de Lima; margen de error ±3,46%, confianza de 95% y pregunta asistida con tarjeta. Blanco/viciado: 5%; no precisa: 9%.</p>
      <h3>Comparación de mediciones de septiembre</h3>
      <div class="poll-table-wrap"><table class="poll-table"><thead><tr><th>Encuestadora y campo</th><th>López Aliaga / RP</th><th>Carlos Bruce</th><th>Francis Allison</th><th>Ficha técnica y lectura</th></tr></thead><tbody>
        <tr><td><strong>CIT</strong><br>2–5 sep.</td><td>33,4%</td><td>12,0%</td><td>11,8%</td><td>500 entrevistas; error ±4,4%. CIT reportó 14,2% de no sabe/no opina.</td></tr>
        <tr><td><strong>IEP</strong><br>4–10 sep.</td><td>20,1%</td><td>17,1%</td><td>4,7%</td><td>350 limeños; error ±5,2%; telefónica y respuesta espontánea. El propio IEP concluyó empate estadístico entre los dos primeros.</td></tr>
        <tr><td><strong>Ipsos</strong><br>24–25 sep.</td><td>25%</td><td>14%</td><td>13%</td><td>803 entrevistas; error ±3,46%; presencial y con tarjeta. Fue la última medición publicable seleccionada.</td></tr>
      </tbody></table></div>
      <details><summary>Fuentes y cómo interpretar la comparación</summary><ul><li>Las preguntas espontáneas y las asistidas con tarjeta no son equivalentes.</li><li>Los márgenes de error y tamaños muestrales varían; no debe promediarse mecánicamente.</li><li>“Liderar” una encuesta describe el momento del trabajo de campo, no predice el resultado electoral.</li><li>López Aliaga figuraba como primer regidor de una lista sin candidato formal a alcalde; se conserva la denominación utilizada por las encuestadoras y se aclara su rol.</li></ul><p><a href="https://www.ipsos.com/es-pe/encuesta-peru-21-ipsos-mayo-2026-intencion-de-voto-para-la-alcaldia-de-lima" target="_blank" rel="noopener">Ipsos de mayo ↗</a> · <a href="https://www.ipsos.com/sites/default/files/ct/news/documents/2026-09/Encuesta%20y%20Simulacro%20Ipsos%20Per%C3%BA%2021%20-%20%20Lima.pdf" target="_blank" rel="noopener">Serie y último informe de Ipsos ↗</a> · <a href="https://estudiosdeopinion.iep.org.pe/wp-content/uploads/2026/09/IEP-Informe-de-opinion-septiembre-ERM-2026.pdf" target="_blank" rel="noopener">Informe completo del IEP ↗</a> · <a href="https://www.citopinion.pe/encuesta-lima-metropolitana-2026-intencion-voto-alcaldia/" target="_blank" rel="noopener">Publicación de CIT ↗</a>.</p></details>
      </details>
    </section>
    <section class="spotlight" aria-labelledby="spotlight-title"><div class="spotlight-head"><div><h2 id="spotlight-title">Los cinco marcados, sin vueltas</h2><p>Una lectura rápida de su experiencia, sus promesas y los asuntos que conviene revisar. La marca sirve para ubicarlos; no significa que sean mejores ni peores.</p></div><span class="spotlight-badge">★ Seguimiento especial</span></div><div class="spotlight-grid" id="spotlight-grid"></div></section>
    <section class="tier-board" id="tier-board" aria-label="Tier list de candidatos"></section>
    <div class="empty" id="empty"><h2>Sin resultados</h2><p>Prueba con otro nombre, partido o estado.</p></div>
  </main>
  <dialog id="profile-dialog" aria-labelledby="modal-name"><div id="modal-content"></div></dialog>
  <footer><span>Fuentes: JNE, Contraloría, Consejo Fiscal, entidades públicas, encuestadoras y prensa enlazada</span><span>Guía ciudadana v8 · Revisión: 03/10/2026 · Los estados y procesos pueden cambiar</span></footer>
  <script id="candidate-data" type="application/json">__DATA__</script>
  <script>
  (()=>{
    const candidates=JSON.parse(document.getElementById('candidate-data').textContent);
    const board=document.getElementById('tier-board'),spotlight=document.getElementById('spotlight-grid'),search=document.getElementById('search'),party=document.getElementById('party'),tabs=document.getElementById('status-tabs'),count=document.getElementById('visible-count'),empty=document.getElementById('empty'),dialog=document.getElementById('profile-dialog'),modal=document.getElementById('modal-content');
    let status='';
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const norm=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const labels={id:'ID',dni:'DNI',nombre:'Nombre completo',edad:'Edad',genero:'Género',partido:'Organización política',partidoId:'ID de organización (JNE)',region:'Región',categoria:'Categoría',cargo:'Cargo',estado:'Estado',numero:'Número',proceso:'Proceso electoral',jurisdiccion:'Jurisdicción',slug:'Código del proceso',fecha:'Fecha',titulo:'Título o grado',universidad:'Institución educativa',anio:'Año',fuente:'Fuente',organizacion:'Organización',elegido:'Elegido/a',ambito:'Ámbito',fechaInicio:'Fecha de inicio',fechaFin:'Fecha de fin',assetType:'Tipo de bien',description:'Descripción',vehiclePlate:'Placa',address:'Dirección',value:'Valor declarado',comment:'Comentario',quantity:'Cantidad',empleador:'Empleador',anioInicio:'Año de inicio',anioFin:'Año de fin',ubicacion:'Ubicación',ruc:'RUC',businessName:'Razón social',commercialName:'Nombre comercial',contributorType:'Tipo de contribuyente',contributorStatus:'Estado del contribuyente',contributorCondition:'Condición del contribuyente',registrationDate:'Fecha de inscripción',hasCoactiveDebt:'Tiene deuda coactiva',coactiveDebts:'Deudas coactivas',amount:'Monto',category:'Categoría',contractingEntity:'Entidad contratante',currency:'Moneda',endDate:'Fecha de término',isConsortium:'Participación en consorcio',oeceCode:'Código OECE',isForeign:'Empresa extranjera',numContracts:'Número de contratos',contractsAmount:'Monto de contratos',numPenalties:'Número de sanciones',sharePercentage:'Porcentaje de participación',relations:'Relaciones declaradas',tcpSanctions:'Sanciones del Tribunal',coactiveDebtAmount:'Monto de deuda coactiva',licenseCategory:'Categoría de licencia',licenseExpiry:'Vencimiento de licencia',licenseStatus:'Estado de licencia',accumulatedPoints:'Puntos acumulados',seriousViolations:'Infracciones graves',verySeriousViolations:'Infracciones muy graves',numPapeletas:'Número de papeletas',numTramites:'Número de trámites',numBonificaciones:'Bonificaciones',caseNumber:'Expediente',caseType:'Tipo de proceso',crime:'Delito o materia',sentence:'Sentencia',sentenceDate:'Fecha de sentencia',court:'Órgano jurisdiccional',modality:'Modalidad',complianceStatus:'Estado de cumplimiento',notes:'Notas'};
    const label=k=>labels[k]||k.replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
    const value=v=>v===null||v===''?'No publicado':v===true?'Sí':v===false?'No':typeof v==='number'?new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(v):String(v);
    const statuses=[...new Set(candidates.map(c=>c.listado.status))];
    const statusCounts=Object.fromEntries(statuses.map(s=>[s,candidates.filter(c=>c.listado.status===s).length]));
    const tierMeta={S:{name:'Perfil muy fuerte',range:'85–100'},A:{name:'Buen punto de partida',range:'70–84'},B:{name:'Tiene pros y contras',range:'55–69'},C:{name:'Hay dudas importantes',range:'40–54'},D:{name:'Muchas alertas',range:'0–39'}};
    const followNames=new Set(['rafael bernardo lopez aliaga cazorla','carlos ricardo bruce montes de oca','francis james allison oyague','daniel belizario urresti elera','samuel marcos daza taype']);
    const isFollow=c=>followNames.has(norm(c.candidato.nombre));
    const confidenceText={Alta:'Mucha',Media:'Suficiente',Baja:'Poca'};
    const plainSummary=s=>String(s||'').replaceAll('resultados verificables','resultados que se pueden comprobar').replaceAll('evidencia independiente','información de fuentes externas').replaceAll('evidencia favorable','información favorable').replaceAll('evidencia limitada','poca información').replaceAll('evidencia insuficiente','no hay suficiente información').replaceAll('gestión ejecutiva municipal comparable','experiencia dirigiendo una municipalidad').replaceAll('gestión municipal ejecutiva','experiencia dirigiendo una municipalidad').replaceAll('gestión pública ejecutiva','experiencia dirigiendo una entidad pública').replaceAll('conducción ejecutiva y presupuestal municipal','haber dirigido una municipalidad y su presupuesto').replaceAll('conducción integral de presupuesto','manejo directo de presupuestos').replaceAll('obligaciones documentales','deudas o pendientes registrados').replaceAll('componente fiscal','nota por manejo del dinero').replaceAll('valoración superior','nota más alta').replaceAll('alerta firme equivalente','problema comprobado parecido');
    const tiers=['S','A','B','C','D'];
    const tierCounts=Object.fromEntries(tiers.map(t=>[t,candidates.filter(c=>c.evaluacion.tier===t).length]));
    document.getElementById('summary').innerHTML=tiers.map(t=>`<div class="metric"><strong>${t}</strong><span>${tierCounts[t]} perfiles · ${tierMeta[t].range}</span></div>`).join('');
    tabs.innerHTML=[`<button class="status-tab" data-status="" aria-pressed="true">Todos · ${candidates.length}</button>`,...statuses.map(s=>`<button class="status-tab" data-status="${esc(s)}" aria-pressed="false">${esc(s)} · ${statusCounts[s]}</button>`)].join('');
    [...new Set(candidates.map(c=>c.listado.party))].sort((a,b)=>a.localeCompare(b,'es')).forEach(p=>party.add(new Option(p,p)));
    const fallback=`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23dfe3e8'/%3E%3Ccircle cx='200' cy='115' r='52' fill='%239ba5b1'/%3E%3Cpath d='M95 300c10-76 50-116 105-116s95 40 105 116' fill='%239ba5b1'/%3E%3C/svg%3E`;
    const spotlightNotes={
      '98':{short:'Rafael López Aliaga',line:'Mucha experiencia y grandes obras en agenda, pero su balance baja por el costo fiscal y los proyectos que todavía no se concretan.',plus:'Ya dirigió la Municipalidad de Lima. Durante su gestión se entregó el primer tramo de la Vía Expresa Sur y avanzaron otras obras viales.',promise:'Hospitales Solidarios, Líneas 3 y 4 del Metro, Tren Chosica–Callao y más servicios municipales digitales.',caution:'El Consejo Fiscal advirtió un riesgo serio por la deuda de Lima. También hay obras financiadas que seguían sin ejecución y cuestionamientos por contratos directos.'},
      '31380':{short:'Carlos Bruce',line:'Es el perfil con más resultados de gestión comprobables entre estos cinco, aunque todavía tiene temas de contratación por aclarar.',plus:'Fue ministro, congresista y alcalde de Surco. Su municipio reportó tres años seguidos ejecutando el 100% del presupuesto destinado a inversiones.',promise:'Usar inteligencia para la seguridad, ayudar a formalizar negocios y darle más capacidad y recursos al gobierno metropolitano.',caution:'Existen cuestionamientos periodísticos sobre contrataciones y obras pendientes. Se muestran como asuntos que deben revisarse, no como una responsabilidad ya probada.'},
      '31372':{short:'Francis Allison',line:'Tiene experiencia municipal directa y resultados visibles en Magdalena, pero las observaciones de control impiden darle una lectura sin reservas.',plus:'Ha sido alcalde de Magdalena en varios periodos. La municipalidad reporta programas para adultos mayores, recuperación de áreas verdes, biblioteca y mejora de espacios públicos.',promise:'Profesionalizar el serenazgo, facilitar la formalización de pequeños negocios, ampliar áreas verdes y reforzar el control interno.',caution:'Debe explicar las observaciones vinculadas al Informe de Contraloría 111-2026 y una alerta que aparece en su ficha electoral.'},
      '31385':{short:'Daniel Urresti',line:'Es una figura muy conocida por seguridad, pero tiene menos experiencia dirigiendo municipios y un antecedente judicial que debe explicarse con precisión.',plus:'Fue ministro del Interior y tiene experiencia nacional en seguridad y política. Es un perfil de alta visibilidad pública.',promise:'Crear una red de cuidados para adultos mayores, formalizar trabajadores y comercios, mejorar el reciclaje y reforzar la lucha anticorrupción.',caution:'El Tribunal Constitucional anuló su condena en el caso Bustíos por prescripción. La decisión no fue una declaración de inocencia sobre los hechos.'},
      '31376':{short:'Samuel Daza',line:'Tiene experiencia reciente como alcalde distrital y obras que se pueden ubicar, aunque falta más verificación externa de sus resultados.',plus:'Como alcalde de Ancón gestionó convenios por más de S/9,5 millones para un parque, pistas y veredas, además de otros proyectos urbanos.',promise:'Recuperar espacios públicos, conectar zonas económicas y logísticas, mejorar el control ambiental y publicar el avance del plan municipal.',caution:'Su ficha registra una alerta sancionadora. Además, buena parte de la información favorable disponible proviene de la propia municipalidad.'}
    };
    const spotlightOrder=['98','31380','31372','31385','31376'];
    spotlight.innerHTML=spotlightOrder.map(id=>{const note=spotlightNotes[id],c=candidates.find(item=>String(item.candidato.id)===id),e=c.evaluacion;return `<article class="spot-card"><div class="spot-person"><img src="${esc(c.localPhoto||fallback)}" alt="Fotografía de ${esc(note.short)}"><div><h3>${esc(note.short)}</h3><span class="spot-meta">${esc(c.listado.party)} · ${esc(e.total)}/100 · grupo ${esc(e.tier)}</span></div></div><p class="spot-line">${esc(note.line)}</p><div class="spot-item"><strong>A su favor</strong><p>${esc(note.plus)}</p></div><div class="spot-item"><strong>Qué promete</strong><p>${esc(note.promise)}</p></div><div class="spot-item caution"><strong>Ojo con esto</strong><p>${esc(note.caution)}</p></div><button class="view" data-id="${esc(id)}">Ver ficha y fuentes</button></article>`}).join('');
    function tierCard(c){const x=c.candidato,e=c.evaluacion,follow=isFollow(c),role=c.rol_lista?'<span class="role-note">1.er regidor · la lista no tiene candidato a alcalde</span>':'';return `<article class="tier-card${follow?' follow-up':''}">${follow?'<span class="follow-marker" title="Marca para encontrarlo rápido; no cambia su puntaje">Seguimiento especial</span>':''}<div class="tier-photo"><img class="portrait" src="${esc(c.localPhoto||fallback)}" alt="Fotografía de ${esc(x.nombre)}" loading="lazy"><img class="party-logo" src="${esc(c.localLogo||fallback)}" alt="Símbolo de ${esc(c.listado.party)}" loading="lazy"><span class="tier-score" title="Puntaje comparativo">${esc(e.total)}</span></div><div class="tier-card-body"><div class="party">${esc(c.listado.party)}</div><h2>${esc(x.nombre)}</h2><div class="status-line">${esc(c.listado.status)}</div>${role}${follow?'<span class="follow-note">Marcado para ubicarlo rápido</span>':''}<span class="research-count">Información encontrada: ${esc(confidenceText[e.confianza]||e.confianza)}</span><button class="view" data-id="${esc(x.id)}">Ver candidato</button></div></article>`}
    function render(){const q=norm(search.value);const visible=candidates.filter(c=>(!q||norm(c.listado.name+' '+c.listado.party).includes(q))&&(!party.value||c.listado.party===party.value)&&(!status||c.listado.status===status)).sort((a,b)=>b.evaluacion.total-a.evaluacion.total||a.candidato.nombre.localeCompare(b.candidato.nombre,'es'));count.textContent=visible.length;empty.style.display=visible.length?'none':'block';board.style.display=visible.length?'grid':'none';board.innerHTML=tiers.map(t=>{const items=visible.filter(c=>c.evaluacion.tier===t);if(!items.length)return '';return `<section class="tier-row tier-${t.toLowerCase()}"><div class="tier-label"><span class="tier-letter">${t}</span><strong>${tierMeta[t].name}</strong><span>${tierMeta[t].range} puntos · ${items.length} perfiles</span></div><div class="tier-cards">${items.map(tierCard).join('')}</div></section>`}).join('')}
    function renderAny(v){if(v===null||v===undefined||v===''||(Array.isArray(v)&&!v.length)||(typeof v==='object'&&!Array.isArray(v)&&!Object.keys(v).length))return '<p class="no-data">Sin información publicada.</p>';if(Array.isArray(v))return `<div class="records">${v.map((x,i)=>`<div class="record">${v.length>1?`<div class="nested"><strong>Registro ${i+1}</strong></div>`:''}${renderAny(x)}</div>`).join('')}</div>`;if(typeof v==='object'){return `<table class="kv"><tbody>${Object.entries(v).map(([k,x])=>`<tr><th>${esc(label(k))}</th><td>${typeof x==='object'&&x!==null?renderAny(x):esc(value(x))}</td></tr>`).join('')}</tbody></table>`}return `<p>${esc(value(v))}</p>`}
    function section(title,v){return `<section class="section"><h3>${esc(title)}</h3>${renderAny(v)}</section>`}
    function openProfile(id){const c=candidates.find(x=>String(x.candidato.id)===String(id));if(!c)return;const x=c.candidato,d=c.detalle||{},contracts=d.contratos||{},debts=d.deudas||{},sanctions=d.sanciones||{},e=c.evaluacion,scoreRows=Object.fromEntries(Object.entries(e.componentes).map(([k,v])=>[`${k} (máx. ${e.maximos[k]})`,v])),auditSources=(e.fuentes_auditoria||[]).map(s=>`<article class="finding"><h4>${esc(s.titulo)}</h4><p><a href="${esc(s.url)}" target="_blank" rel="noopener">Abrir fuente ↗</a></p></article>`).join('')||'<p class="no-data">No se encontró una fuente externa específica adicional; la valoración se apoya en la ficha electoral y se marca con confianza baja.</p>',role=c.rol_lista?`<span class="pill changed">1.er regidor · encabeza lista sin candidato a alcalde</span>`:'';modal.innerHTML=`<header class="modal-head"><img class="modal-photo" src="${esc(c.localPhoto||fallback)}" alt=""><div><h2 id="modal-name">${esc(x.nombre)}</h2><p class="modal-party">${esc(x.partido)}</p></div><button class="close" aria-label="Cerrar">×</button></header><div class="modal-body"><div class="profile-intro"><span class="pill">Tier ${esc(e.tier)} · ${esc(e.total)}/100</span><span class="pill changed">Confianza: ${esc(e.confianza)}</span>${role}<span class="pill">${esc(x.edad)} años</span><span class="pill">DNI ${esc(x.dni)}</span><span class="pill">${esc(c.listado.status)}</span></div><section class="section"><div class="research-box"><h3>Conclusión de auditoría · 03/10/2026</h3><p>${esc(e.resumen_auditoria)}</p>${auditSources}</div></section>${section('Desglose de la auditoría',scoreRows)}${section('Candidatura y proceso',x.candidaturas)}${section('Educación y títulos declarados',d.educacion)}${section('Trayectoria política',d.trayectoria)}${section('Afiliaciones políticas',d.afiliaciones)}<section class="section"><h3>Contratos, actividad económica y empresas</h3><h4>Información SUNAT</h4>${renderAny(contracts.sunat)}<h4>Contratos con el Estado</h4>${renderAny(contracts.govContracts)}<h4>Derechos mineros</h4>${renderAny(contracts.miningRights)}<h4>Empresas relacionadas</h4>${renderAny(contracts.empresas)}</section>${section('Propiedades declaradas',d.propiedades)}<section class="section"><h3>Deudas y obligaciones</h3><h4>Deudas alimentarias</h4>${renderAny(debts.alimentarias)}<h4>Deudas judiciales</h4>${renderAny(debts.judiciales)}<h4>Licencia, infracciones y papeletas</h4>${renderAny(debts.drivingRecord)}</section><section class="section"><h3>Sanciones y sentencias declaradas</h3><h4>Sentencias</h4>${renderAny(sanctions.sentencias)}<h4>Registro de abogados sancionados</h4>${renderAny(sanctions.rnas)}<h4>Sanciones SERVIR</h4>${renderAny(sanctions.servir)}<h4>Sanciones OECE</h4>${renderAny(sanctions.oeceSanctions)}</section>${section('Experiencia laboral declarada',d.experienciaLaboral)}<p class="source-note">Ficha electoral: <a href="${esc(c.url)}" target="_blank" rel="noopener">Revisa Tu Candidato</a></p></div>`;dialog.showModal();modal.querySelector('.close').focus()}
    tabs.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;status=b.dataset.status;tabs.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render()});search.addEventListener('input',render);party.addEventListener('change',render);board.addEventListener('click',e=>{const b=e.target.closest('.view');if(b)openProfile(b.dataset.id)});spotlight.addEventListener('click',e=>{const b=e.target.closest('.view');if(b)openProfile(b.dataset.id)});dialog.addEventListener('click',e=>{if(e.target===dialog||e.target.closest('.close'))dialog.close()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&dialog.open)dialog.close()});render();
    function openProfile(id){
      const c=candidates.find(item=>String(item.candidato.id)===String(id));if(!c)return;
      const x=c.candidato,d=c.detalle||{},e=c.evaluacion,contracts=d.contratos||{},debts=d.deudas||{},sanctions=d.sanciones||{},supplement=c.investigacion?.suplemento||{},plan=c.propuestas||{},follow=isFollow(c);
      const education=Array.isArray(d.educacion)?d.educacion:[],trajectory=Array.isArray(d.trayectoria)?d.trayectoria:[],jobs=Array.isArray(d.experienciaLaboral)?d.experienciaLaboral:[];
      const educationCount=Math.max(education.length,Number(supplement.educacion||0)),jobCount=Math.max(jobs.length,Number(supplement.experienciaLaboral||0));
      const elected=trajectory.filter(item=>item.elegido).length,govContracts=Array.isArray(contracts.govContracts)?contracts.govContracts:[];
      const formalSignals=['sentencias','rnas','servir'].reduce((n,k)=>n+(Array.isArray(sanctions[k])?sanctions[k].length:0),0)+(Array.isArray(debts.alimentarias)?debts.alimentarias.length:0)+(Array.isArray(debts.judiciales)?debts.judiciales.length:0);
      const traffic=Number(debts.drivingRecord?.numPapeletas||0),role=c.rol_lista?'<span class="pill changed">1.er regidor · la lista no tiene candidato a alcalde</span>':'';
      const scoreNames={'Capacidad y experiencia':'Experiencia para el cargo','Resultados verificables':'Resultados que se pueden comprobar','Gestión fiscal y contratación':'Manejo del dinero y contratos','Integridad y cumplimiento':'Problemas comprobados','Transparencia e institucionalidad':'Transparencia'};
      const scoreRows=Object.entries(e.componentes).map(([name,val])=>{const max=e.maximos[name],pct=Math.round((val/max)*100);return `<div class="score-row"><span>${esc(scoreNames[name]||name)}</span><span class="score-track"><span class="score-fill" style="width:${pct}%"></span></span><span class="score-number">${val}/${max}</span></div>`}).join('');
      const sources=(e.fuentes_auditoria||[]).map(s=>`<article class="source-card"><strong>${esc(s.titulo)}</strong><a href="${esc(s.url)}" target="_blank" rel="noopener">Ver de dónde sale ↗</a></article>`).join('')||'<div class="empty-brief">Para esta nota usamos principalmente la ficha electoral.</div>';
      const topicNames={'Social':'Personas y seguridad','Económica':'Trabajo y economía','Ambiental':'Ambiente y limpieza','Institucional':'Cómo funcionaría la municipalidad'};
      const proposalCards=(plan.propuestas||[]).map(item=>`<article class="proposal-card"><span class="proposal-topic">${esc(topicNames[item.tema]||item.tema)}</span><h4>${esc(item.propuesta)}</h4>${item.meta?`<details><summary>Ver la meta que promete</summary><p>${esc(item.meta)}</p></details>`:''}</article>`).join('');
      const timeline=[];
      education.forEach(item=>timeline.push(`<article class="timeline-card"><strong>${esc(item.titulo||'Estudio declarado')}</strong><p>${esc(item.universidad||'Institución no publicada')}</p><span>Educación${item.anio?' · '+esc(item.anio):''}</span></article>`));
      trajectory.forEach(item=>timeline.push(`<article class="timeline-card"><strong>${esc(item.cargo||'Participación política')}</strong><p>${esc(item.organizacion||item.jurisdiccion||'Organización no publicada')}</p><span>${esc(item.proceso||'Proceso electoral')}${item.elegido?' · Elegido/a':''}</span></article>`));
      jobs.forEach(item=>timeline.push(`<article class="timeline-card"><strong>${esc(item.cargo||'Experiencia laboral')}</strong><p>${esc(item.empleador||'Empleador no publicado')}</p><span>${esc(item.anioInicio||'')} ${item.anioFin?'– '+esc(item.anioFin):''}</span></article>`));
      (c.investigacion?.hallazgos||[]).forEach(item=>timeline.push(`<article class="timeline-card"><strong>${esc(item.titulo||'Verificación adicional')}</strong><p>${esc(item.detalle||'')}</p><span>${esc(item.fuente||'Fuente externa verificada')}</span></article>`));
      const raw=(title,value)=>`<details class="raw-group"><summary>${esc(title)}</summary><div>${renderAny(value)}</div></details>`;
      modal.innerHTML=`
        <header class="profile-hero"><img class="profile-portrait" src="${esc(c.localPhoto||fallback)}" alt="Fotografía de ${esc(x.nombre)}"><div class="profile-title"><h2 id="modal-name">${esc(x.nombre)}</h2><p>${esc(x.partido)} · ${esc(c.listado.status)} · grupo ${esc(e.tier)} · ${esc(e.total)}/100 · información ${esc((confidenceText[e.confianza]||e.confianza).toLowerCase())}</p></div><div class="profile-score">${esc(e.total)}<small>Grupo ${esc(e.tier)}</small></div><button class="close" aria-label="Cerrar">×</button></header>
        <div class="profile-shell"><div class="profile-intro"><span class="pill">${esc(x.edad)} años</span><span class="pill">DNI ${esc(x.dni)}</span>${role}${follow?'<span class="pill" style="border-color:#7046b8;color:#5d379c;font-weight:800">★ Seguimiento especial</span>':''}</div>
        <div class="quick-facts"><div class="quick-fact"><strong>${educationCount}</strong><span>estudios encontrados</span></div><div class="quick-fact"><strong>${trajectory.length}</strong><span>participaciones políticas</span></div><div class="quick-fact"><strong>${elected}</strong><span>veces que fue elegido</span></div><div class="quick-fact"><strong>${jobCount}</strong><span>trabajos declarados</span></div><div class="quick-fact"><strong>${govContracts.length}</strong><span>contratos con el Estado</span></div><div class="quick-fact"><strong>${(e.fuentes_auditoria||[]).length}</strong><span>fuentes clave revisadas</span></div></div>
        <nav class="profile-tabs" aria-label="Secciones del perfil"><button class="profile-tab" data-panel="propuestas" aria-selected="true">Qué propone</button><button class="profile-tab" data-panel="resumen" aria-selected="false">En pocas palabras</button><button class="profile-tab" data-panel="trayectoria" aria-selected="false">Qué ha hecho</button><button class="profile-tab" data-panel="integridad" aria-selected="false">Qué debería explicar</button><button class="profile-tab" data-panel="expediente" aria-selected="false">Ver todos los datos</button></nav>
        <section class="profile-panel active" data-tab-panel="propuestas"><div class="proposal-intro"><div><h3>Algunas propuestas de su plan</h3><p>Tomamos una por cada tema del resumen presentado al JNE. Son promesas de campaña y no cambian el puntaje.</p></div><a class="plan-link" href="${esc(plan.plan_url||'https://votoinformado.jne.gob.pe/')}" target="_blank" rel="noopener">Ver plan completo ↗</a></div>${proposalCards?`<div class="proposal-grid">${proposalCards}</div>`:'<div class="no-proposals">No encontramos un plan oficial disponible para esta lista en Voto Informado.</div>'}</section>
        <section class="profile-panel" data-tab-panel="resumen"><div class="dashboard"><article class="verdict"><h3>En pocas palabras</h3><p>${esc(plainSummary(e.resumen_auditoria))}</p></article><article class="score-panel"><h3>¿De dónde salen sus ${esc(e.total)} puntos?</h3>${scoreRows}</article></div><h3 class="panel-title" style="margin-top:1rem">¿De dónde salió esta información?</h3><div class="source-grid">${sources}</div></section>
        <section class="profile-panel" data-tab-panel="trayectoria"><h3 class="panel-title">Sus estudios, trabajos y pasos por la política</h3><div class="timeline">${timeline.join('')||'<div class="empty-brief">No encontramos trayectoria publicada en las fuentes consultadas.</div>'}</div></section>
        <section class="profile-panel" data-tab-panel="integridad"><h3 class="panel-title">Datos para mirar con calma</h3><div class="signal-grid"><div class="signal-card"><strong>${formalSignals}</strong><span>casos registrados en las bases consultadas</span></div><div class="signal-card"><strong>${traffic}</strong><span>papeletas registradas</span></div><div class="signal-card"><strong>${govContracts.length}</strong><span>contratos con el Estado encontrados</span></div></div><p class="signal-note">Que aparezca cero no significa que la persona tenga un certificado de buena conducta: solo quiere decir que no encontramos registros en estas bases. Una investigación tampoco significa que alguien sea culpable.</p>${raw('Sentencias y sanciones',sanctions)}${raw('Deudas registradas',debts)}${raw('Contratos y negocios',contracts)}</section>
        <section class="profile-panel" data-tab-panel="expediente"><h3 class="panel-title">Todos los datos disponibles</h3>${raw('Su candidatura',x.candidaturas)}${raw('Estudios',education)}${raw('Pasos por la política',trajectory)}${raw('Partidos a los que perteneció',d.afiliaciones)}${raw('Trabajos declarados',jobs)}${raw('Propiedades',d.propiedades)}${raw('Contratos y empresas',contracts)}${raw('Deudas',debts)}${raw('Sanciones',sanctions)}<p class="source-note">Ficha electoral: <a href="${esc(c.url)}" target="_blank" rel="noopener">abrir en Revisa Tu Candidato ↗</a></p></section></div>`;
      dialog.showModal();modal.querySelector('.close').focus();
    }
    dialog.addEventListener('click',e=>{const tab=e.target.closest('.profile-tab');if(!tab)return;modal.querySelectorAll('.profile-tab').forEach(item=>item.setAttribute('aria-selected',String(item===tab)));modal.querySelectorAll('.profile-panel').forEach(panel=>panel.classList.toggle('active',panel.dataset.tabPanel===tab.dataset.panel))});
    if(location.hash.startsWith('#candidate-'))openProfile(location.hash.slice(11));
    document.addEventListener('click',e=>{const a=e.target.closest('a[href^="https://"]');if(!a)return;e.preventDefault();e.stopPropagation();const url=a.getAttribute('href');const opened=window.open('about:blank','_blank');if(opened){opened.opener=null;opened.location.replace(url)}else{window.prompt('El navegador bloqueó la pestaña. Copia este enlace:',url)}},true);
  })();
  </script>
</body>
</html>'''.replace("__DATA__", data_json).replace("__DATE__", extracted_date)


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    replacement_payload = json.loads(REPLACEMENTS.read_text(encoding="utf-8"))
    research_payload = json.loads(RESEARCH.read_text(encoding="utf-8"))
    audit_payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    proposals_payload = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    research_by_id = research_payload.get("candidatos", {})
    audit_by_id = audit_payload.get("candidatos", {})
    proposals_by_party = proposals_payload.get("partidos", {})
    audit_maxima = audit_payload["metadata"]["maximos"]
    candidates = payload["candidatos"]
    replacements_by_old_id = {item["sustituye_id"]: item for item in replacement_payload.get("candidatos", [])}
    candidates = [replacements_by_old_id.get(item["candidato"]["id"], item) for item in candidates]
    ASSETS.mkdir(parents=True, exist_ok=True)
    logo_cache: dict[str, str] = {}

    for index, record in enumerate(candidates, 1):
        listed = record["listado"]
        candidate = record["candidato"]
        stem = f"{index:02d}-{slugify(candidate['nombre'])}"
        photo_rel = f"assets/{stem}.webp"
        photo_path = DIST / photo_rel
        if not photo_path.exists():
            download_webp(candidate.get("foto") or listed.get("photoUrl"), photo_path)
        record["localPhoto"] = photo_rel if photo_path.exists() else listed.get("photoUrl")

        party_key = str(listed.get("partyJneId") or listed.get("partyId") or slugify(listed["party"]))
        if party_key not in logo_cache:
            logo_rel = f"assets/partido-{party_key}.webp"
            logo_path = DIST / logo_rel
            if not logo_path.exists():
                download_webp(listed.get("partyLogoUrl"), logo_path, square=True)
            logo_cache[party_key] = logo_rel if logo_path.exists() else listed.get("partyLogoUrl")
        record["localLogo"] = logo_cache[party_key]
        research = research_by_id.get(str(candidate["id"]), {"resumen": "Sin hallazgos adicionales.", "suplemento": {}, "hallazgos": []})
        documentary_score = score_candidate(record, research)
        audit = audit_by_id[str(candidate["id"])]
        record["investigacion"] = research
        record["evaluacion_documental_retirada"] = documentary_score
        record["evaluacion"] = score_audit(audit, audit_maxima)
        record["propuestas"] = proposals_by_party.get(
            str(listed.get("partyJneId")),
            {
                "partido": listed.get("party"),
                "propuestas": [],
                "plan_url": "https://votoinformado.jne.gob.pe/",
                "fuente": "Jurado Nacional de Elecciones · Voto Informado",
            },
        )
        print(f"[{index:02d}/{len(candidates):02d}] {candidate['nombre']}")

    safe_json = json.dumps(candidates, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    raw_date = payload.get("metadata", {}).get("fecha_extraccion", "2026-10-02")
    extracted_date = raw_date[:10].split("-")
    extracted_date = "/".join(reversed(extracted_date)) if len(extracted_date) == 3 else raw_date
    html = html_template(safe_json, extracted_date)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    print(f"\nSitio generado: {DIST / 'index.html'}")


if __name__ == "__main__":
    main()
