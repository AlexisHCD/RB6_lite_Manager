# ADR-0008: Persistencia segura — backups, verificación y rollback

- **Estado:** Aceptada
- **Fecha:** 2026-08-12
- **Fase:** 5

## Contexto

La escritura atómica de [ADR-0006](0006-app-config-toml-xdg-atomic-write.md)
evitaba truncados, pero sin backups versionados. Los overrides de WirePlumber
exigían el contrato `IConfigRepository` sin implementación. La Etapa 5
requiere dry-run, backup, verificación y rollback antes de aplicar cualquier
cambio de configuración.

## Decisión

1. **Config de la app (TOML XDG):** `save_config` crea un backup timestamped
   antes de reemplazar un archivo existente (por defecto
   `~/.local/share/openbuds/backups/config.<ts>.bak`), escribe atómicamente
   (temp + fsync + `os.replace`), verifica el resultado con `load_config` y,
   si la verificación falla, restaura automáticamente el backup
   (`auto_rollback_on_error` del `AppConfig` / flag `auto_rollback`). `dry_run`
   renderiza y devuelve el TOML sin efectos. `backup_config_file` y
   `restore_config_file` son públicos; `restore` pre-valida el TOML del backup
   antes de instalar y verifica tras instalar.
2. **Overrides de WirePlumber:** `WirePlumberConfigEditor` implementa
   `IConfigRepository` (`read_override`/`write_override` → `ConfigBackup`/
   `restore_from_backup`/`list_backups`) exclusivamente bajo
   `~/.config/wireplumber/`, con validación estricta de rutas (rechaza
   absolutas, traversal `..`, backslashes/drives de Windows y NUL), backup
   flat timestamped antes de escribir, verificación de contenido con rollback
   automático y restore validado dentro del alcance XDG. Sin archivo previo →
   `backup_path` vacío (rollback imposible, error claro).
3. **CLI:** `config get` (efectiva), `config set <clave> <valor>
   [--dry-run]` (5 claves; bool acepta `true`/`false`/`sí`/`no`/`1`/`0`),
   `config backup`, `config backups` (timestamp UTC + tamaño + ruta) y
   `config restore <archivo.bak>`; exit 0 en éxito, `ConfigError` → 1.
4. **Scope:** nada se escribe fuera del alcance XDG del usuario; nunca con
   root.

## Alternativas

- No implementar backups: descartada, viola los requisitos de la Etapa 5.
- Backups de directorios enteros: descartada, sobredimensionada para el caso.
- Compresión de backups: innecesaria.

## Consecuencias

- **Positivas:** todo cambio es reversible, dry-run seguro, contrato
  `IConfigRepository` cumplido y probado.
- **Negativas:** dos copias por escritura y latencia de `fsync`;
  `list_backups` estima el `original_path` por el nombre base (para restaurar
  con garantías se usa el `ConfigBackup` devuelto por `write_override`).

## Verificación

Tests unitarios de backup, rollback, restore, dry-run y traversal de rutas,
más un smoke de integración aislado con `XDG_CONFIG_HOME`/`XDG_DATA_HOME`
temporales (config real del usuario no tocada). Gates: 560 unit / 575
integración opt-in; Ruff, mypy y diff-check en verde.
