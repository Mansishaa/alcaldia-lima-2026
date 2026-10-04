# Extracción de candidatos a la Alcaldía de Lima

Fuente: <https://www.revisatucandidato.pe>

Alcance: 27 candidaturas a **alcalde provincial de Lima, Lima** para las ERM 2026. La extracción conserva todos los estados publicados por la fuente, incluidas candidaturas admitidas, inscritas, improcedentes o con renuncia.

Fecha de extracción: 2026-10-02 (America/Lima).

## Archivos

- `alcaldes_lima_completo.json`: registro íntegro y anidado de cada perfil. Incluye datos generales, candidatura, educación, trayectoria, afiliaciones, información SUNAT, contratos públicos, derechos mineros, empresas, propiedades, deudas, historial de conducción, sanciones, sentencias y experiencia laboral, cuando la fuente los publica.
- `alcaldes_lima_resumen.csv`: una fila por candidato con los campos principales y conteos por sección. Está codificado como UTF-8 con BOM para abrirse correctamente en Excel.
- `alcaldes_lima_detalle.csv`: versión normalizada de toda la información. Cada fila contiene la ruta del campo (`ruta`) y su valor, vinculados por ID y DNI del candidato.

## Consideraciones

- Los datos reflejan el estado del sitio al momento de la extracción y pueden cambiar durante el proceso electoral.
- Un valor vacío significa que la fuente no publicó un dato en ese campo; no debe interpretarse automáticamente como “no tiene”.
- El DNI y demás datos personales aquí contenidos ya estaban publicados en las fichas públicas de candidatos. Su reutilización debe respetar la finalidad de investigación y la normativa aplicable.
- Para actualizar los archivos, ejecutar desde la carpeta del proyecto: `python .\extraer_alcaldes_lima.py`.
