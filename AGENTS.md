# AGENTS.md — Guía maestra para agentes y desarrolladores

> **Este es el archivo fuente de verdad del proyecto.** Cualquier agente IA o
> desarrollador que trabaje en OpenBuds Manager debe leer y respetar este
> documento antes de escribir código. Las decisiones técnicas detalladas viven
> en `docs/ADR/` y se resumen aquí.

---

## 1. Identidad del proyecto

**OpenBuds Manager** — aplicación de escritorio para gestionar auriculares
Bluetooth en Linux (Ubuntu 24.04 LTS). El primer dispositivo objetivo es
**Redmi Buds 6 Lite**. La prioridad es entregar una aplicación usable y segura,
no una biblioteca genérica ni una colección de adaptadores.

- **Repositorio:** https://github.com/AlexisHCD/RB6_lite_Manager.git
- **Remoto (push):** `git@github.com:AlexisHCD/RB6_lite_Manager.git` (SSH)
- **SO objetivo:** Ubuntu 24.04 LTS (Noble Numbat)
- **Runtime objetivo:** `/usr/bin/python3` de Ubuntu 24.04 (Python 3.12), con
  acceso a PyGObject/Gio mediante paquetes del sistema.
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
2. **Nunca** enviar comandos Bluetooth propietarios o desconocidos.
3. **Nunca** aplicar ingeniería inversa directamente sobre el dispositivo.
4. **Nunca** modificar hardware.
5. **Nunca** eliminar configuraciones existentes del sistema sin backup.
6. **Nunca** sobrescribir archivos sin crear backup previo.
7. **Nunca** asumir soporte para un códec o capacidad del dispositivo.
8. **Todo** cambio sobre el sistema Linux debe poder revertirse.
9. **Nunca** ejecutar OTA ni modificar firmware del dispositivo o del adaptador.
10. **Nunca** eliminar emparejamientos ni cambiar `Trusted`, `Blocked` o
    `Pairable` automáticamente.
11. **Nunca** escribir en `/usr/share`, `/etc` ni usar `sudo` sin aprobación
    explícita del usuario.
12. **Nunca** reiniciar servicios, conectar/desconectar hardware, cambiar un
    perfil real ni escribir configuración sin explicar antes la acción y recibir
    aprobación explícita.

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
- El usuario supervisa el desarrollo. Las lecturas, tests, lint, mypy,
  consultas estrictamente de solo lectura y correcciones internas aprobadas no
  requieren confirmación adicional.
- Se requiere aprobación explícita antes de cambiar contratos públicos
  importantes, instalar dependencias, usar `sudo`, escribir configuración,
  reiniciar servicios, controlar hardware real, cambiar perfiles, crear commits,
  hacer push, crear ramas/tags/releases o ampliar el alcance actual.

---

## 7. Gestión del repositorio y commits

- **Repositorio único:** todo el código pertenece a
  `git@github.com:AlexisHCD/RB6_lite_Manager.git`. Nunca crear proyectos
  paralelos ni revisar carpetas fuera de
  `/home/alexdev/proyectos/RedmiBuds6LinuxAPP`.
- **Push por SSH** (la llave SSH está configurada en la máquina anfitriona).
- Estructura de carpetas limpia (ver §10).
- **Commits pequeños y atómicos:** un commit = una funcionalidad o mejora.
  Nunca mezclar varias funcionalidades importantes en un mismo commit.
- **Mensaje de commit:** conventional commits en inglés
  (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- Los commits se hacen únicamente tras aprobación explícita del usuario.
- Documentar decisiones arquitectónicas importantes mediante ADRs en `docs/ADR/`.

### Flujo de trabajo por tarea

1. Implementar **una** tarea (módulo/funcionalidad).
2. `ruff check` + `ruff format --check` + `mypy src` + `pytest` deben pasar.
3. Mostrar resumen, archivos, validaciones, límites y riesgos pendientes.
4. Detenerse para revisión.
5. Tras aprobación explícita: `git add`, commit descriptivo y push por SSH.

---

## 8. Workflow de implementación (regla más importante)

**No intentes construir toda la aplicación de una sola vez.** Construye el
proyecto como lo haría un equipo profesional:

1. Analiza.
2. Investiga.
3. Pregunta todas las dudas necesarias.
4. Diseña la arquitectura base (ya definida; sin fase antigua).
5. Documenta las decisiones (ADRs).
6. Implementa **un único módulo**.
7. Prueba ese módulo.
8. Corrige errores.
9. Presenta el resultado y detente para revisión.
10. Haz commit/push solo si el usuario lo aprueba explícitamente.

---

## 9. Prioridades del proyecto

### Prioridad máxima
Aplicación usable · Seguridad · Estabilidad · Estado real del dispositivo ·
Backend sólido · Interfaz simple · Health Check · Backups y rollback.

### Prioridad media
Información del dispositivo · Nivel general de batería · RSSI · Códec activo ·
Perfil Bluetooth · Estado del micrófono · Información del adaptador ·
Notificaciones · Benchmark · Logs.

### Fuera del alcance actual
OTA · firmware · comandos propietarios · escritura GATT propietaria. La
ingeniería inversa, si alguna vez se justifica, será exclusivamente pasiva.

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
| [0005](docs/ADR/0005-device-profile-contract.md) | Perfiles de dispositivo en YAML | Objetivo declarativo; contrato y YAML actuales incompatibles, rediseño tipado pendiente de aprobación. |
| [0006](docs/ADR/0006-app-config-toml-xdg-atomic-write.md) | Configuración TOML con rutas XDG y escritura atómica | Configuración propia separada, rutas XDG válidas y guardado sin truncado. |
| [0007](docs/ADR/0007-device-change-event-contract.md) | Contrato de eventos de cambio de dispositivo (`DeviceChangeEvent`) | `DeviceChangeKind`/`DeviceChangeEvent`/`Unsubscribe`; contrato del dominio probado; **Incremento 2 completo**: nivel bajo de señales/lifecycle y dispatch del repositorio (`subscribe_device_changes`) implementados y verificados (fakes + integración real de lifecycle A/B). |
| [0008](docs/ADR/0008-safe-persistence.md) | Persistencia segura — backups, verificación y rollback | Configuración XDG, escritura atómica y restauración reversible; sin root. |
| [0009](docs/ADR/0009-optional-qt-tray-and-gio-notifications.md) | Bandeja Qt opcional y notificaciones Gio | `QSystemTrayIcon` opcional y `org.freedesktop.Notifications` best-effort; base previa para el puente de eventos de ADR-0010. |
| [0010](docs/ADR/0010-qt-device-change-notifications.md) | Notificaciones Qt automáticas de cambios de dispositivos | `DeviceChangeBridge` con `Qt.QueuedConnection`, política significativa, sanitización, degradación segura y lifecycle idempotente. |

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

El contrato actual y el YAML todavía son incompatibles. Antes de implementar el
loader se debe presentar para aprobación una propuesta tipada que distinga
fuente, evidencia, fecha y nivel de verificación (`standard_guaranteed`,
`vendor_claimed`, `runtime_observed`, `hardware_verified`, `unknown`). Publicado
por el fabricante no equivale a verificado en hardware. No asumir HSP, hardware
volume, batería GATT ni codec switching; OTA queda fuera del alcance absoluto.

Ver [ADR-0005](docs/ADR/0005-device-profile-contract.md).

---

## 15. Roadmap orientado al producto

| Etapa | Estado | Resultado |
|------|--------|-----------|
| 0 — Estabilización | 🔜 En curso | Runtime reproducible, doctor fiable, WpctlAdapter cerrado, CI y licencia |
| 1 — Caracterización física pasiva | ⏳ | Evidencia real de BlueZ/PipeWire/WirePlumber sin controlar hardware |
| 2 — Backend de sesión | ⏳ | Estado agregado, CLI y controles estándar aprobados |
| 3 — GUI MVP | ⏳ | Una ventana útil PySide6; bandeja después del MVP |
| 4 — Health Check | ⏳ | Diagnóstico con observado/inferido/no disponible |
| 5 — Persistencia segura | ⏳ | Dry-run, backup, escritura atómica, verificación y rollback |

Detalle en `docs/ROADMAP.md`.

---

## 16. Ámbito de trabajo

- **Directorio de trabajo exclusivo:**
  `/home/alexdev/proyectos/RedmiBuds6LinuxAPP`
- No revisar ni modificar carpetas fuera de este directorio.
- El `venv` vive en `.venv/` (ignorado por git).

---

## 17. Documentación

- Documentar cambios visibles, contratos públicos, riesgos, evidencia empírica,
  decisiones difíciles de revertir e instrucciones necesarias para ejecutar.
- `ROADMAP.md` es breve y orientado a resultados; `README.md` refleja el estado
  y uso actuales; un ADR se reserva para decisiones importantes y duraderas.
- No duplicar contratos, documentar validaciones triviales ni mantener conteos
  exactos de tests que se vuelven obsoletos.
- Los docstrings explican intención o riesgo; no repiten el código.

---

## 18. Mínima intervención y evitar sobreingeniería

- Flujo de cambios sobre Linux: **observar → diagnosticar → explicar → proponer
  → aprobar → backup → aplicar → verificar → revertir si falla**.
- Hasta probar backup y rollback, solo se permiten lecturas o cambios efímeros
  de sesión previamente aprobados.
- Implementar necesidades actuales y rebanadas verticales; no crear plugins,
  pantallas, DTO, parsers o repositorios sin un consumidor real inmediato.
- Una abstracción nueva debe aislar una API externa, una frontera de seguridad o
  resolver más de un uso real; si una solución directa es clara, usarla.
- Tests proporcionales al comportamiento y al riesgo; evitar probar detalles
  privados irrelevantes o multiplicar casos equivalentes.
- No hacer refactors amplios ni añadir dependencias durante un incremento
  funcional sin justificación y aprobación.
