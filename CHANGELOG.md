# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con [SemVer](https://semver.org/lang/es/).

## [0.2.0] - 2026-10-11

### Añadido
- Elissa tiene cuerpo: un personaje propio dibujado en código, con 14 expresiones, efectos y transiciones suaves.
  Sigue el cursor con la mirada en todo el escritorio, parpadea, reacciona si la tocas (clic derecho), si dejas el
  ratón encima o si la arrastras, celebra al terminar una respuesta y se duerme si no la usas.
- 18 sonidos propios, sintetizados; cada uno se puede reemplazar con un archivo y el volumen se ajusta en Ajustes.
- Ícono, pantalla de carga y colores nuevos a partir del personaje.
- Ventana nativa (Tauri): burbuja transparente que se expande al conversar y vuelve a encogerse, se arrastra
  desde la cara, vive en la bandeja del sistema y puede iniciar con Windows.
- Actualizaciones automáticas firmadas: Elissa avisa cuando hay una versión nueva y se actualiza con un clic.
- Reconocimiento de voz con Groq, OpenAI o un servidor Whisper propio, con su clave en Ajustes → Voz.
- `elissa.exe --quit` cierra la instancia en ejecución guardando la conversación.

### Cambiado
- Los datos (ajustes, memoria, registros) pasan a `%APPDATA%\Elissa`; se migran solos desde la versión anterior.
- El micrófono solo se abre mientras escucha y se libera a los 20 segundos.
- Instalador nuevo (NSIS por usuario, sin permisos de administrador).

### Seguridad
- El motor local solo acepta a la ventana de Elissa (token por sesión y verificación de origen).

### Corregido
- Títulos de conversación que copiaban la plantilla cuando el modelo local era pequeño.
- Escribir mientras escuchaba podía dejar la interfaz en reposo durante la respuesta.

## [0.1.0] - 2026-10-10

- Primera versión: asistente de voz con cualquier proveedor de IA, archivos, web, correo de solo lectura y memoria.
