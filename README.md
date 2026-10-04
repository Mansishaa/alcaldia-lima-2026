# Alcaldía de Lima 2026 — auditoría visual

Sitio de investigación y comparación de las listas para la Alcaldía Provincial de Lima en las Elecciones Regionales y Municipales 2026.

## Contenido

- Tier list basada en capacidad, resultados verificables, gestión fiscal, integridad y transparencia.
- Fichas visuales de 27 perfiles con fuentes enlazadas.
- Identificación diferenciada de candidatos a alcalde y primeros regidores de listas sin candidato formal.
- Encuestas históricas anteriores a la veda, separadas del puntaje de gestión.
- Expediente electoral completo disponible bajo demanda.

## Estructura

- `sitio_alcaldes_lima/dist/`: sitio estático publicado.
- `crear_html_alcaldes_lima.py`: generador del sitio.
- `auditoria_gestion.json`: puntuación y fuentes de la auditoría.
- `investigacion_adicional.json`: hallazgos complementarios.
- `salida/`: extracción base de candidatos y primeros regidores.

## Regenerar el sitio

```powershell
python crear_html_alcaldes_lima.py
```

La publicación en GitHub Pages se ejecuta automáticamente al enviar cambios a `main`.

## Alcance

El puntaje es una metodología comparativa y no constituye una recomendación de voto. Las investigaciones preliminares se presentan como tales y no como declaraciones de culpabilidad.

