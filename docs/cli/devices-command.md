# Diseño técnico — CLI `devices` (incremento snapshot)

Diseño del comando `openbuds devices`: lista los dispositivos Bluetooth
**conocidos** por el sistema a partir del snapshot `GetManagedObjects` de BlueZ.

- **Fase:** 3 (Bluetooth)
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado; se conserva
  como documentación viva)
- **Estado del checkbox roadmap:** el ítem *"CLI `devices`"*
  ([ROADMAP §Fase 3](../ROADMAP.md)) está **marcado `[x]`**: el incremento se
  implementó y verificó, y el checklist del roadmap y el README se actualizaron
  al cerrar este incremento.
- **Documentos relacionados:** [Diseño del repositorio BlueZ](../bluez/repository-design.md)
  (consultas snapshot sobre las que se construye este comando),
  [Contrato del mapper](../bluez/object-mapper-contract.md),
  [Interfaces D-Bus de BlueZ](../bluez/dbus-interfaces.md), [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md),
  [AGENTS.md](../../AGENTS.md) §5 (investigación antes de asumir) y §3 (no
  escritura en el dispositivo).
- **Dependencias del dominio:** `ScanDevicesRequest` / `ScanDevicesUseCase`
  (`application/scan_devices.py`), `IBluetoothRepository`
  (`domain/interfaces/bluetooth_repo.py`), `DeviceInfo`
  (`domain/models/device.py`), `BluetoothError` (`core/errors.py`).

> **Alcance:** este comando es de **solo lectura**. **No** inicia discovery ni
> escaneo activo (`Adapter1.DiscoveryStart`), **no** conecta (`Device1.Connect`)
> y **no** depende de señales (`subscribe_device_changes` no se usa; no hay
> GLib main loop). Únicamente lee los objetos ya conocidos por `bluetoothd`
> mediante el snapshot del repositorio ([repository-design §5.3](../bluez/repository-design.md#53-no-mutación)).

> **Estado de implementación (2026-08-09):** este incremento está
> **implementado y verificado**. `openbuds devices` se compone en `main` con
> `_build_scan_devices_use_case` (`BlueZRepository` + `ScanDevicesUseCase`),
> **solo** para el comando `devices` y **tras** cargar configuración y logging
> (composición explícita, [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md);
> los tests inyectan/monkeypatchean la factory, sin GI ni bus). Acepta
> `-p|--paired-only` y `-a|--adapter ADAPTER` con `type=` que normaliza `hciN`
> → `/org/bluez/hciN` y valida `^hci\d+$` (§2). Imprime TSV en español con
> cabecera, sanitización y privacidad (§3–§4). El TDD (§7) está **completado**
> y la suite suma **192 passed, 4 skipped** (las 4 omisiones son integraciones
> opt-in desactivadas por defecto). El smoke opt-in (§8) pasó en **Python 3.12
> / Gio** sobre BlueZ real: exit 0, sin patrones MAC ni `dev_` en stdout/stderr
> y sin auto-arrancar `bluetoothd` (solo lectura). El comando es **solo
> snapshot**: no discovery, no connect y **sin señales** (no depende del
> Incremento 2).

---

## 1. Composición y dependencias

```
cli/main.py  (_cmd_devices)
  └─> application.ScanDevicesUseCase.execute(ScanDevicesRequest)
        └─> IBluetoothRepository.list_devices(adapter_path)
              └─> BlueZRepository (snapshot fresco, sin cache)
```

- El handler construye el `ScanDevicesRequest` a partir de los flags y delega
  en el caso de uso. No contiene lógica de negocio (presentación pura).
- `CliContext` **no** instancia `BlueZRepository` como default. Solo cuando el
  comando es `devices` —y **tras** cargar configuración y logging— `main`
  compone explícitamente `BlueZRepository` (único punto que importa `gi` en
  esta ruta) y `ScanDevicesUseCase`, y lo pasa al handler.
- Los tests **no** importan `gi` ni tocan el bus: inyectan un fake o
  monkeypatchean la factory de construcción del repositorio (p. ej.
  `main._build_repository`) antes de invocar `main`/el handler.
- Cumple [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md): la
  presentación depende de la aplicación, que depende solo del contrato del
  dominio.

---

## 2. Flags exactos

```
openbuds devices [-h] [-p|--paired-only] [-a|--adapter ADAPTER]
```

| Flag | Tipo | Efecto | Request |
|------|------|--------|---------|
| `--paired-only`, `-p` | store_true | Solo dispositivos emparejados | `include_paired_only=True` |
| `--adapter ADAPTER`, `-a ADAPTER` | `type=` propio de argparse | Restringe a un adaptador; acepta `hciN` **o** `/org/bluez/hciN` | `adapter_path="/org/bluez/hciN"` (normalizado) |

- Sin flags → todos los dispositivos de todos los adaptadores
  (`adapter_path=None`, `include_paired_only=False`).
- El `type` de argparse **valida y normaliza** `ADAPTER`: si recibe `hciN` lo
  convierte a `/org/bluez/hciN`; si recibe `/org/bluez/hciN` lo conserva. En
  ambos casos aplica una **regex estricta** `^hci\d+$` sobre el basename (tras
  quitar el prefijo `/org/bluez/`). Cualquier otra forma (`foo`, `hci`,
  `hci0/extra`, sufijos `dev_...`, MAC, etc.) es inválida.
- **Valor inválido → `argparse.ArgumentTypeError` → exit 2**, y esto ocurre
  **antes** del bootstrap (antes de `load_config`/logging) y **antes** de
  importar `gi`/`BlueZRepository`: el fallo de uso nunca llega al bus.
- El contrato del repositorio filtra por `object_path` **exacto**
  ([repository-design §4.2](../bluez/repository-design.md#42-list_devicesadapter_path-str--none--none---listdeviceinfo)),
  por lo que el request siempre lleva la ruta completa ya normalizada.
- Otros errores de uso (flag desconocido, valor ausente) → `argparse` con
  exit 2.

---

## 3. Formato de salida

TSV en español con **cabecera** y una línea por dispositivo, en el **orden que
devuelve el repositorio** (ordenado por `object_path`):

```
NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR
<display_name>\t<connection>\t<pairing>\t<adapter>
```

| Campo | Fuente (`DeviceInfo`) | Valores |
|-------|----------------------|---------|
| `display_name` | `alias` si no vacío, si no `name`, si no **`Dispositivo sin nombre`** | texto sanitizado (ver §4) |
| `connection` | `connected` | `conectado` \| `desconectado` |
| `pairing` | `paired` | `emparejado` \| `no emparejado` |
| `adapter` | basename de `adapter_path` (p. ej. `hci0`) | texto sanitizado; vacío si no hay |

Los tokens `conectado`/`desconectado`/`emparejado`/`no emparejado` y el
fallback `Dispositivo sin nombre` son constantes del propio CLI (derivadas de
booleanos o del fallback), no texto del dispositivo: no requieren sanitización.

El separador `\t` es **seguro por construcción**: la sanitización (§4) sustituye
cada carácter de control de los campos por `?`, de modo que un `\t` nunca puede
aparecer dentro de un campo.

Ejemplo:

```
NOMBRE	CONEXIÓN	EMPAREJAMIENTO	ADAPTADOR
Redmi Buds 6 Lite	conectado	emparejado	hci0
Mi auricular	desconectado	emparejado	hci0
Dispositivo sin nombre	desconectado	no emparejado	hci1
```

**Caso vacío:** si la lista es `[]`, se imprime a stdout **solo** el mensaje
`No se encontraron dispositivos Bluetooth.` (sin cabecera, sin filas) y se
devuelve **exit 0** (no es un error).

---

## 4. Privacidad y sanitización

1. **Nunca** se imprime `DeviceInfo.address` (MAC) ni `DeviceInfo.object_path`.
   El `display_name` nunca cae a un identificador del dispositivo: si no hay
   `alias` ni `name`, se usa el fallback constante **`Dispositivo sin nombre`**.
2. Todo campo de texto dinámico (`display_name`, `adapter`) se trata como **no
   confiable** porque procede de D-Bus, y se sanitiza exactamente así:
   - cada carácter no imprimible o de control (incluye tab, newline, CR, ESC y
     cualquier otro `C0`/`C1`) se reemplaza **individualmente** por `?` — no se
     colapsa a espacio ni se fusionan secuencias consecutivas;
   - tras sustituir, el campo se trunca a **80 codepoints** (no bytes).
3. `adapter` se reduce al **basename** `hciN` ya validado por el `type` de
   argparse (§2): nunca aparece como ruta `/org/bluez/...`.
4. Los tokens `conectado`/`desconectado`/`emparejado`/`no emparejado` y el
   fallback `Dispositivo sin nombre` son constantes del propio CLI: no
   requieren sanitización.
5. Los logs del comando no incluyen MAC ni `object_path` (se verifica en tests
   y smoke, §7).

---

## 5. Códigos de salida

| Código | Caso |
|--------|------|
| 0 | Éxito (con o sin dispositivos) |
| 1 | `OpenBudsError` — incl. `BluetoothError` de snapshot/mapeo: `main` lo captura, loguea (si logging configurado) e imprime `Error: <msg>` en stderr |
| 2 | Uso inválido (`argparse`) o subcomando desconocido |

`BluetoothError` es subclase de `OpenBudsError`
([core/errors.py](../../src/openbuds/core/errors.py)); el `except OpenBudsError`
de `main` ya cubre el caso sin cambios adicionales
([cli/main.py](../../src/openbuds/cli/main.py)).

---

## 6. Bootstrap y ausencia de señales

- `devices` pasa a formar parte de `_BOOTSTRAP_COMMANDS` (junto a
  `doctor`/`config`): `main` carga configuración y logging antes de ejecutar el
  handler, y el `except OpenBudsError` central devuelve 1. Tras ese bootstrap,
  y **solo** para `devices`, `main` compone explícitamente `BlueZRepository` y
  `ScanDevicesUseCase` antes de llamar al handler (§1).
- El comando **no** se suscribe a `subscribe_device_changes`, **no** arranca un
  main loop de GLib y **no** depende del Incremento 2 de señales: usa solo la
  consulta snapshot `list_devices`.
- Al implementar, `_cmd_future` deja de listar `devices` y el test
  parametrizado `test_future_command_returns_two_with_real_phase`
  (`tests/unit/test_cli.py`) se actualiza (se elimina `devices` del caso). **Ya
  hecho:** `devices` no aparece en `_cmd_future` y el test parametrizado quedó
  reducido a `codec`/`health`/`bench`.

---

## 7. Criterios TDD (completados)

### 7.1 Caso de uso — `tests/unit/test_scan_devices.py`

| # | Caso | Esperado |
|---|------|----------|
| 1 | sin filtros | `list_devices(None)`; se devuelven todos |
| 2 | `adapter_path` | se pasa **tal cual** al repositorio |
| 3 | `include_paired_only=True` | solo dispositivos `paired` |
| 4 | `include_paired_only=True` y todos `paired` | se conservan todos |
| 5 | repositorio devuelve `[]` | `[]` |
| 6 | repositorio lanza `BluetoothError` | **se propaga** (misma instancia, sin tragarse) |
| 7 | orden | el caso de uso **no reordena**: conserva el orden del repositorio |

### 7.2 CLI — `tests/unit/test_cli_devices.py` (con fake, sin GI ni bus)

| # | Caso | Esperado |
|---|------|----------|
| 1 | sin flags | `adapter_path=None`, `include_paired_only=False`; cabecera + una línea por dispositivo |
| 2 | `--adapter hci0` | request con `adapter_path="/org/bluez/hci0"` |
| 3 | `--adapter /org/bluez/hci1` | se normaliza igual → `adapter_path="/org/bluez/hci1"` |
| 4 | `--adapter` inválido (`foo`, `hci`, `hci0/extra`, `/org/bluez/hci0/dev_xx`, MAC) | `argparse.ArgumentTypeError` → exit 2, **sin** bootstrap ni import de `gi` |
| 5 | `--paired-only` | `include_paired_only=True` |
| 6 | ambos flags | se aplican ambos filtros |
| 7 | escape/newline | `alias`/`name` con `\n`, `\t`, `\r`, ESC y otros control → cada carácter → `?`; el TSV no se rompe; **no** se colapsa a espacio |
| 8 | truncado | campo de texto > 80 codepoints → exactamente 80 |
| 9 | privacidad | MAC y `object_path` del fake **nunca** aparecen en stdout ni en logs |
| 10 | fallback de nombre | `alias` y `name` vacíos → `display_name` = `Dispositivo sin nombre` |
| 11 | cabecera y tokens | cabecera `NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR`; valores `conectado`/`desconectado`, `emparejado`/`no emparejado` |
| 12 | lista vacía | solo el mensaje `No se encontraron dispositivos Bluetooth.` en stdout (sin cabecera) y exit 0 |
| 13 | `BluetoothError` | exit 1 y `Error: <msg>` en stderr |
| 14 | sin señales | el comando nunca invoca `subscribe_device_changes` del repo inyectado |

El fake del repositorio implementa solo `list_devices` (y opcionalmente cuenta
llamadas); si el CLI intentara usar señales fallaría por atributo ausente, lo
que convierte el caso 14 en una garantía estructural. Los tests que ejercitan
`main` (no solo el handler) inyectan o monkeypatchean la factory de
construcción del repositorio (p. ej. `main._build_repository`) y nunca llegan
a importar `gi`.

### 7.3 Implementación de `main` (ajuste a `tests/unit/test_cli.py`)

- `test_future_command_returns_two_with_real_phase`: quitar `devices` de la
  parametrización (deja de ser un comando futuro). **Ya hecho** (solo
  `codec`/`health`/`bench`).

---

## 8. Smoke real opt-in

- `tests/integration/test_cli_devices_smoke.py`, marcado
  `@pytest.mark.integration` (desactivado salvo `OPENBUDS_RUN_INTEGRATION=1`).
- Ejecuta el comando con `BlueZRepository` real (o el entry point vía
  subprocess) y verifica:
  - sin excepciones; el stdout respeta el formato TSV (cabecera + filas);
  - **privacidad:** no hay patrones MAC (`XX:XX:XX:XX:XX:XX`) ni rutas
    `/org/bluez/.../dev_` en stdout ni en los logs capturados;
  - la lectura no auto-arranca `bluetoothd` (hereda los flags
    `DO_NOT_AUTO_START`/`NO_AUTO_START` del cliente
    [repository-design §8](../bluez/repository-design.md#8-integración-real-solo-lectura--verificada)).
- El smoke puede **verificar** la ausencia/presencia de patrones MAC y `dev_`,
  pero **no inspecciona ni imprime** los valores sensibles capturados: las
  aserciones son de regex sobre el flujo, sin volcar el contenido al reporte ni
  a los logs.
- Es un smoke de lectura: nunca se llama a métodos mutadores.

**Verificado 2026-08-09:** el smoke pasó en **Python 3.12 / Gio** sobre el
BlueZ real del sistema: `openbuds devices` devolvió exit 0, sin patrones MAC ni
`dev_` en stdout/stderr, y sin auto-arrancar `bluetoothd` (solo lectura).

---

## 9. Ubicación en el árbol

```
src/openbuds/cli/main.py                 # _cmd_devices, flags+type, bootstrap, composición explícita del repo  [implementado]
src/openbuds/application/scan_devices.py # caso de uso (implementado)  [implementado]
tests/unit/test_scan_devices.py          # TDD del caso de uso  [implementado]
tests/unit/test_cli_devices.py           # TDD del CLI (inyecta/monkeypatchea la factory, sin GI)  [implementado]
tests/integration/test_cli_devices_smoke.py  # smoke opt-in  [implementado, verificado]
```

---

## 10. Resumen de decisiones (registro del arquitecto)

1. **Solo snapshot de objetos conocidos**: no discovery, no connect, no
   escritura ([AGENTS.md §3](../../AGENTS.md#3-filosofía-no-negociable)).
2. **Composición explícita en `main`:** `CliContext` **no** instancia
   `BlueZRepository` como default; solo para `devices`, tras config/logging,
   `main` compone `BlueZRepository` + `ScanDevicesUseCase`. Tests con fake o
   monkeypatch de la factory, sin GI/bus.
3. **Flags exactos:** `-p|--paired-only` y `-a|--adapter ADAPTER`, con `type=`
   que acepta `hciN` o `/org/bluez/hciN`, valida `^hci\d+$` sobre el basename y
   normaliza a la ruta completa; inválido → exit 2 **antes** de bootstrap/GI.
4. **Salida TSV en español con cabecera**
   `NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR`; tokens `conectado`/
   `desconectado`, `emparejado`/`no emparejado`; fallback `Dispositivo sin
   nombre`; caso vacío con **solo** el mensaje a stdout y **exit 0**.
5. **Privacidad:** nunca MAC ni `object_path`; `adapter` solo basename `hciN`
   validado.
6. **Sanitización:** cada carácter no imprimible/control (incluye tab/newline/
   ESC) → `?`; 80 codepoints máx por campo de texto.
7. **`BluetoothError`/`OpenBudsError` → exit 1** vía el `except` central de
   `main`; errores de uso (incl. `ADAPTER` inválido) → 2.
8. **Sin señales ni main loop** en este incremento.
9. Roadmap (checkbox CLI `devices` `[x]`), README y baseline (**192 passed, 4
   skipped**) se actualizaron **al cerrar el incremento de implementación**.
