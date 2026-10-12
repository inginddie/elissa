# Política de firma de código

Firma de código gratuita provista por [SignPath.io](https://about.signpath.io/), certificado de
[SignPath Foundation](https://signpath.org/).

## Qué se firma

Solo se firman binarios construidos desde el código de este repositorio: el instalador de Elissa
(`Elissa_x.y.z_x64-setup.exe`) y los programas que instala. Los construye GitHub Actions en runners alojados por GitHub
con el workflow público
[`.github/workflows/release.yml`](https://github.com/inginddie/elissa/blob/main/.github/workflows/release.yml).
Los componentes de terceros que vienen con Elissa (por ejemplo el runtime y las librerías de Python, o los modelos que
se descargan) no se firman con este certificado.

## Roles del equipo

| Rol | Miembros |
|---|---|
| Committers y revisores | [Diego Bustos (@inginddie)](https://github.com/inginddie) |
| Aprobadores | [Diego Bustos (@inginddie)](https://github.com/inginddie) |

- Los committers pueden cambiar el código.
- Los cambios de cualquier otra persona llegan como pull requests, y un revisor debe aprobarlos antes de integrarlos.
- Un aprobador aprueba a mano cada solicitud de firma.
- Cada miembro usa autenticación multifactor en GitHub y SignPath.

La lista actual de personas con permiso de escritura está en
[los colaboradores del repositorio](https://github.com/inginddie/elissa/graphs/contributors).

## Privacidad

Elissa envía datos solo a los servicios que eliges, y solo para las funciones que usas: tu proveedor de IA, tu
servicio de reconocimiento de voz y el servicio de voz. La [política de privacidad](privacy.md) lista cada uno y cómo
apagarlo. El instalador muestra un resumen antes de instalar.

*La versión oficial de esta política es la [versión en inglés](https://github.com/inginddie/elissa/blob/main/docs/CODE_SIGNING.md).*
