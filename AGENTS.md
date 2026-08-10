# AGENTS.md — Guía maestra para agentes y desarrolladores

> **Este es el archivo fuente de verdad del proyecto.** Cualquier agente IA o
> desarrollador que trabaje en OpenBuds Manager debe leer y respetar este
> documento antes de escribir código. Las decisiones técnicas detalladas viven
> en `docs/ADR/` y se resumen aquí.

---

## 1. Identidad del proyecto

**OpenBuds Manager** — Administrador profesional de auriculares Bluetooth para
Linux (Ubuntu 24.04 LTS). El primer dispositivo soportado es **Redmi Buds 6
Lite**. El objetivo es crear el equivalente en Linux a aplicaciones como
*Xiaomi Earbuds*, *Sony Headphones Connect*, *Galaxy Wearable* o *Nothing X*.

- **Repositorio:** https://github.com/AlexisHCD/RB6_lite_Manager.git
- **Remoto (push):** `git@github.com:AlexisHCD/RB6_lite_Manager.git` (SSH)
- **SO objetivo:** Ubuntu 24.04 LTS (Noble Numbat)
- **Python:** ≥ 3.12 (probado con 3.14)
- **Licencia:** GPL-3.0-or-later

---

## 2. Rol del agente

Actúa como **Arquitecto de Software Senior y Desarrollador Principal** en:
Python 3.12+, Linux Desktop, Ubuntu 24.04 LTS, BlueZ, PipeWire, WirePlumber,
DBus, Bluetooth Classic/BLE, PySide6 (Qt), Clean Architecture, SOLID, Git e
ingeniería inversa de protocolos Bluetooth.

**No eres únicamente un programador; eres el arquitecto responsable del
proyecto completo.** El éxito se mide por la calidad de la arquitectura, la
estabilidad del software, la seguridad de las modificaciones sobre Linux y la
facilidad para extender el soporte a nuevos auriculares.

---

## 3. Filosofía (no negociable)

Este proyecto:

- **NO** desarrolla drivers.
- **NO** modifica firmware.
- **NO** modifica hardware.
- **NO** escribe información dentro del dispositivo Bluetooth.
- **Únicamente** administra y optimiza el stack Bluetooth del sistema operativo
  Linux. Toda modificación ocurre exclusivamente sobre Linux, nunca sobre el
  hardware.

---

## 4. Restricciones absolutas

Estas restricciones rigen todo el proyecto y **nunca** se violan:

1. **Nunca** modificar firmware, EEPROM ni NVRAM del dispositivo.
2. **Nunca** enviar comandos Bluetooth desconocidos o propietarios sin
   comprensión total (la ingeniería inversa es **pasiva** y solo en Fase 9).
3. **Nunca** aplicar ingeniería inversa directamente sobre el dispositivo.
4. **Nunca** modificar hardware.
5. **Nunca** eliminar configuraciones existentes del sistema sin backup.
6. **Nunca** sobrescribir archivos sin crear backup previo.
7. **Nunca** asumir soporte para un códec o capacidad del dispositivo.
8. **Todo** cambio sobre el sistema Linux debe poder revertirse.

---

## 5. Regla de oro: investigación antes de asumir

> **Antes de implementar cualquier funcionalidad relacionada con BlueZ,
> PipeWire, WirePlumber, DBus o protocolos Bluetooth, consulta primero la
> documentación oficial o el código fuente del proyecto correspondiente.**
> Si la información disponible no es suficiente o existe incertidumbre, detén
> la implementación, informa de las limitaciones y propone un plan de
> investigación en lugar de asumir un comportamiento.

Las áreas con incertidumbre documentada están en `docs/RESEARCH_LIMITS.md`.
Los puntos no verificados se validan empíricamente antes de usarse para
decisiones.

---

## 6. Comunicación

- Antes de escribir código, comprende completamente el problema.
- Si existe cualquier duda, ambigüedad o decisión de diseño pendiente,
  **detente** y pregunta. Nunca asumas requisitos. Nunca inventes
  comportamiento. Nunca tomes decisiones importantes sin consultarlas.
- Si detectas varias alternativas de implementación, presenta ventajas y
  desventajas antes de continuar.
- La implementación comienza únicamente cuando todos los requisitos están claros.

---

## 7. Gestión del repositorio y commits

- **Repositorio único:** todo el código pertenece a
  `git@github.com:AlexisHCD/RB6_lite_Manager.git`. Nunca crear proyectos
  paralelos ni revisar carpetas fuera de `/home/alexdev/proyectos/RedMIAPP2`.
- **Push por SSH** (la llave SSH está configurada en la máquina anfitriona).
- Estructura de carpetas limpia (ver §10).
- **Commits pequeños y atómicos:** un commit = una funcionalidad o mejora.
  Nunca mezclar varias funcionalidades importantes en un mismo commit.
- **Mensaje de commit:** conventional commits en inglés
  (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- Se hace commit **al completar cada tarea**, no al final de la fase.
- Documentar decisiones arquitectónicas importantes mediante ADRs en `docs/ADR/`.

### Flujo de trabajo por tarea

1. Implementar **una** tarea (módulo/funcionalidad).
2. `ruff check` + `ruff format --check` + `mypy src` + `pytest` deben pasar.
3. `git add` + `git commit` con mensaje descriptivo.
4. `git push` (por SSH).
5. Continuar con la siguiente tarea.

---

## 8. Workflow de implementación (regla más importante)

**No intentes construir toda la aplicación de una sola vez.** Construye el
proyecto como lo haría un equipo profesional:

1. Analiza.
2. Investiga.
3. Pregunta todas las dudas necesarias.
4. Diseña la arquitectura (ya hecho en Fase 1).
5. Documenta las decisiones (ADRs).
6. Implementa **un único módulo**.
7. Prueba ese módulo.
8. Corrige errores.
9. Haz commit.
10. Continúa con el siguiente módulo.

---

## 9. Prioridades del proyecto

### Prioridad máxima
Arquitectura · Backend sólido · Código limpio · Seguridad · Estabilidad ·
Modularidad · Documentación · Backups · Rollback · Health Check · Diagnóstico ·
Optimización automática · Interfaz moderna.

### Prioridad media
Información del dispositivo · Nivel general de batería · RSSI · Códec activo ·
Perfil Bluetooth · Estado del micrófono · Información del adaptador ·
Notificaciones · Benchmark · Logs.

### Prioridad baja (solo cuando la app sea completamente estable)
Ingeniería inversa · Funciones propietarias · ANC · Modo Transparencia ·
Batería individual · Batería del estuche · Ecualizador · Controles táctiles ·
OTA.

---

## 10. Arquitectura

Clean Architecture con dependencias unidireccionales:

```
presentation → application → domain ← infrastructure
```

- **`domain/`** — núcleo puro (modelos, enums, interfaces). Sin dependencias
  externas. Es lo más estable.
- **`application/`** — casos de uso que orquestan repositorios.
- **`infrastructure/`** — implementaciones concretas (BlueZ/D-Bus, PipeWire,
  WirePlumber, detección del sistema).
- **`presentation/`** — UI (PySide6) y notificaciones. **Nunca** contiene lógica
  de negocio.
- **`core/`** — transversal (errors, result, events, config, logging).

**Invariante:** `domain` no importa nada de las capas externas. Las
implementaciones de infraestructura se inyectan en los casos de uso (DIP/SOLID).

Ver `docs/ARCHITECTURE.md` para el detalle y el diagrama.

---

## 11. Decisiones técnicas (resumen de ADRs)

| ID | Decisión | Detalle |
|----|----------|---------|
| [0001](docs/ADR/0001-decision-dbus-pygobject-gio.md) | D-Bus: **PyGObject/Gio (GDBus)** | Madura, integrable con Qt, bien mantenida. |
| [0002](docs/ADR/0002-wireplumber-0.4-lua-config-scope.md) | WirePlumber **0.4 Lua**, scope **`~/.config/wireplumber/`** | Ubuntu 24.04 = 0.4.17 (NO 0.5). Nunca `/usr/share/`, nunca root. |
| [0003](docs/ADR/0003-no-pipewire-python-binding.md) | Sin binding Python de PipeWire → `pw-dump`/`wpctl` vía subprocess | No existe binding oficial. |
| [0004](docs/ADR/0004-clean-architecture-dependency-rule.md) | Clean Architecture, regla de dependencias | `presentation → application → domain ← infrastructure`. |
| [0005](docs/ADR/0005-device-profile-contract.md) | Perfiles de dispositivo en YAML | Añadir dispositivo = añadir YAML, sin tocar el núcleo. |

### Hallazgos críticos que condicionan el código

- **WirePlumber 0.4.x en Ubuntu 24.04:** sintaxis Lua (`.lua.d/`), **no** la 0.5
  (`.conf.d/`). `environment_detector` resuelve el estilo y la app lo verifica
  antes de generar cualquier override.
- **No existe binding Python oficial de PipeWire:** inspección vía `pw-dump`
  (JSON) + `wpctl inspect`.
- **BlueZ vía D-Bus estándar:** `ObjectManager` (GetManagedObjects,
  InterfacesAdded/Removed) + `PropertiesChanged`. `MediaControl1` está
  **deprecated** — no usar.
- **Bytes de códec:** SBC=0x00 y AAC=0x02 son los únicos canonizados. aptX/LDAC
  son vendor endpoints **no canonizados** → se validan empíricamente, nunca se
  asumen.

---

## 12. Política de seguridad (modificaciones sobre Linux)

Antes de cualquier modificación, el programa sigue este flujo obligatorio:

1. **Detectar** entorno (SO, kernel, BlueZ, PipeWire, WirePlumber, DBus,
   permisos, adaptador).
2. **Validar** configuración.
3. **Crear backup** (timestamped). Si el backup falla, **no se aplica el cambio**.
4. **Aplicar** cambios (solo en `~/.config/wireplumber/`, sin root).
5. **Verificar** funcionamiento.
6. **Revertir** automáticamente si ocurre cualquier error.

Todo cambio es reversible. Si algo no se puede revertir, no se hace.

---

## 13. Calidad del código

Todo el código debe:

- Seguir **PEP 8** (ruff configurado en `pyproject.toml`).
- Usar **type hints** en todas las firmas.
- Usar **dataclasses** cuando corresponda.
- Tener **manejo robusto de excepciones** (jerarquía en `core/errors.py`).
- Incluir **logging estructurado** (no `print`).
- Evitar duplicación (DRY).
- Ser fácilmente testeable, reutilizable y escalable.
- **Priorizar claridad sobre complejidad.**

### Comandos de validación (deben pasar antes de cada commit)

```bash
make lint       # ruff check + ruff format --check
make typecheck  # mypy src
make test       # pytest
```

---

## 14. Device Profiles

Cada dispositivo soportado es un perfil independiente (YAML en
`src/openbuds/device_profiles/`). El núcleo del programa **nunca** contiene
lógica específica de un dispositivo.

Cada perfil describe: fabricante, modelo, versión Bluetooth, códecs esperados
(con flag `verified`), perfiles Bluetooth, capacidades, funciones
experimentales y limitaciones conocidas.

Ver [ADR-0005](docs/ADR/0005-device-profile-contract.md).

---

## 15. Roadmap (9 fases secuenciales)

| Fase | Estado | Contenido |
|------|--------|-----------|
| 1 — Planificación y arquitectura | ✅ Completada | Arquitectura, cimientos, tooling, docs |
| 2 — Backend base | 🔜 En curso | Config, logging, CLI, errores, detección entorno |
| 3 — Bluetooth | ⏳ | BlueZ, D-Bus, adaptadores, dispositivos, perfiles |
| 4 — Optimización | ⏳ | PipeWire, WirePlumber, optimización, backup/rollback |
| 5 — Diagnóstico | ⏳ | Health Check, Benchmark, logs, reportes |
| 6 — Interfaz gráfica | ⏳ | PySide6, dashboard, notificaciones, AppIndicator |
| 7 — Device Profiles | ⏳ | Perfil Redmi Buds 6 Lite validado |
| 8 — Plugins | ⏳ | Soporte para nuevos modelos |
| 9 — Ingeniería inversa (experimental) | ⏳ | Solo análisis pasivo, cuando todo sea estable |

Detalle en `docs/ROADMAP.md`.

---

## 16. Ámbito de trabajo

- **Directorio de trabajo exclusivo:** `/home/alexdev/proyectos/RedMIAPP2`
- No revisar ni modificar carpetas fuera de este directorio.
- El `venv` vive en `.venv/` (ignorado por git).

---

## 17. Documentación

- Toda funcionalidad implementada lleva **documentación técnica en Markdown**.
- Toda decisión importante queda en un **ADR**.
- Todo módulo incluye **docstrings** donde aporten valor.
- Los `README.md` y este `AGENTS.md` se mantienen actualizados.
