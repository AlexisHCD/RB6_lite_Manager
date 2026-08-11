# ADR-0006: Configuración TOML con rutas XDG y escritura atómica

- **Estado:** Aceptada
- **Fecha:** 2026-08-09
- **Fase:** 2

## Contexto

La configuración propia de OpenBuds debe estar separada de la configuración
del sistema y funcionar correctamente en entornos que personalizan las rutas
XDG. El lector ya usa `tomllib` de la biblioteca estándar, pero Python no
incluye un escritor TOML. Además, una escritura directa puede truncar el
archivo válido si el proceso falla durante el guardado.

## Decisión

La configuración de la aplicación se guarda como TOML bajo:

- `XDG_CONFIG_HOME/openbuds/config.toml`, usando `~/.config` como fallback.
- `XDG_DATA_HOME/openbuds`, usando `~/.local/share` como fallback.

Cada variable XDG solo se acepta si está presente, no está vacía y contiene
una ruta absoluta. No se carga ningún archivo `.env`.

La lectura usa `tomllib` y conserva el merge con defaults y la ignorancia de
campos desconocidos para forward compatibility. La escritura sigue siendo
manual para conservar comentarios, pero los strings se serializan con
`json.dumps(..., ensure_ascii=False)`. JSON y los TOML basic strings comparten
los escapes usados aquí para comillas, backslashes, saltos de línea y
caracteres de control; el unicode legible se conserva.

El archivo se escribe en un temporal del mismo directorio, se vacía con
`flush` y `fsync`, y se instala con `os.replace`. El temporal se limpia
best-effort si falla cualquier paso. Esta configuración propia no crea backups
versionados: la atomicidad evita el truncado y los backups obligatorios de
configuración del sistema corresponden a la Etapa 5.

## Alternativas

- `tomli-w`: descartada porque añade una dependencia innecesaria para un
  formato pequeño y estable.
- `Path.write_text` directo: descartada porque puede dejar un archivo
  truncado ante un fallo de escritura.
- Ignorar XDG y usar siempre `Path.home()`: descartada porque no respeta la
  configuración estándar del entorno de escritorio.

## Consecuencias

- **Positivas:** rutas configurables y testeables, roundtrip seguro de strings,
  preservación del archivo anterior ante fallos de reemplazo y ausencia de
  dependencias nuevas.
- **Negativas:** el serializador manual debe actualizarse si aparecen nuevos
  tipos de configuración; `fsync` puede añadir una pequeña latencia al guardado.

## Verificación

Las pruebas unitarias cubren valores XDG absolutos e inválidos, errores de
lectura, creación de directorios, escritura y reemplazo, preservación del
destino anterior, limpieza de temporales y roundtrip de comillas, backslashes,
controles y unicode.
