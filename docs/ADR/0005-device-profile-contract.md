# ADR-0005: Contrato de perfiles de dispositivo

- **Estado:** Aceptada
- **Fecha:** 2026-07-02
- **Fase:** 1

## Contexto

El proyecto debe soportar múltiples modelos de auriculares (comenzando por
Redmi Buds 6 Lite) sin que el núcleo del programa contenga lógica específica de
un dispositivo. Cada dispositivo tiene características distintas: códecs
soportados, perfiles Bluetooth, capacidades (batería, ANC, EQ), limitaciones.

## Decisión

Modelar cada dispositivo soportado como un **perfil independiente** en formato
**YAML**, cargado en tiempo de ejecución por `IDeviceProfileRepository`.

### Contrato del perfil

Cada perfil YAML describe:

| Campo | Descripción |
|-------|-------------|
| `profile_id` | Identificador estable (`redmi_buds_6_lite`) |
| `manufacturer` | Fabricante |
| `model` | Modelo comercial |
| `bluetooth_version` | Versión Bluetooth soportada |
| `supported_codecs` | Códecs esperados (con flag `verified`) |
| `bluetooth_profiles` | Perfiles Bluetooth (A2DP, HFP, HSP, AVRCP) |
| `capabilities` | Funciones disponibles conocidas |
| `experimental_features` | Funciones experimentales (no estables) |
| `known_limitations` | Limitaciones conocidas |
| `match_hints` | Heurísticas de resolución (OUI, patrones de nombre) |

### Clase del dominio

`DeviceProfile` (en `domain/interfaces/profile_repo.py`) define la forma que
todo perfil cargado debe satisfacer. La implementación concreta de carga y
validación vive en `device_profiles/loader.py` (Fase 7).

## Justificación

1. **Extensibilidad sin tocar el núcleo:** añadir un dispositivo = añadir un
   archivo YAML. No se modifica código del dominio ni de la aplicación.
2. **Declarativo:** YAML es legible y editable por usuarios avanzados, sin
   compilar.
3. **Seguridad:** los campos `verified` marcan qué datos están validados
   empíricamente. Los códecs vendor (aptX, LDAC) se marcan `verified: false`
   hasta confirmación en dispositivo real (ver [`RESEARCH_LIMITS.md`](../RESEARCH_LIMITS.md)).
4. **Separación de responsabilidades:** la descripción estática del dispositivo
   vive en datos (YAML); la lógica de resolución vive en código.

## Resolución de dispositivo → perfil

`IDeviceProfileRepository.match_device(device)` asocia un `DeviceInfo` detectado
con su perfil usando heurísticas declarativas (`match_hints`):

- **OUI prefixes:** los primeros 3 octetos de la MAC (asignación IEEE).
- **Patrones de nombre:** coincidencia con `Device1.Name` / `Device1.Alias`.

Devuelve `None` si no hay perfil conocido.

## Consecuencias

- **Positivas:** soporte multi-dispositivo escalable y declarativo.
- **Negativas:** la resolución heurística puede dar falsos positivos/negativos
  (se mitiga con múltiples pistas y validación empírica en Fase 7).
- **Plugins (Fase 8):** los plugins podrán registrar perfiles adicionales en
  runtime, respetando el mismo contrato.

## Primer perfil

`device_profiles/redmi_buds_6_lite.yaml` — documentado de forma **conservadora**:
los campos no verificados se marcan explícitamente. El proyecto **nunca** envía
comandos propietarios al dispositivo (ver filosofía del proyecto y Fase 9).
