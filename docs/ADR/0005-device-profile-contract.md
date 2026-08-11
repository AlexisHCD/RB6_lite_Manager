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

> **Aviso de estado actual:** esta decisión es histórica y se mantiene como
> objetivo, pero **no está implementada**. `DeviceProfile` y el YAML actual son
> **incompatibles**. El loader está **bloqueado** hasta que se apruebe una
> propuesta tipada del contrato (fuente, evidencia, fecha y nivel de
> verificación) y exista evidencia de la Etapa 1. La tabla de campos siguiente
> es el **diseño original**, no un contrato operativo actual.

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
validación vivirá en `device_profiles/loader.py` cuando se apruebe la propuesta
tipada del contrato y exista evidencia de la Etapa 1.

## Justificación

1. **Extensibilidad sin tocar el núcleo (objetivo/resultado esperado):** añadir
   un dispositivo debería equivaler a añadir un archivo YAML sin modificar
   código del dominio ni de la aplicación. Aún no es una capacidad actual.
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
  (se mitiga con múltiples pistas y validación empírica en la Etapa 1).
- **Plugins:** fuera del roadmap inmediato. Cualquier registro futuro de perfiles
  en runtime queda condicionado a que el contrato tipado se apruebe
  previamente; no se promete ninguna capacidad de plugins en este ADR.

## Primer perfil

`device_profiles/redmi_buds_6_lite.yaml` — documentado de forma **conservadora**:
los campos no verificados se marcan explícitamente. El proyecto **nunca** envía
comandos propietarios al dispositivo (ver filosofía del proyecto).
