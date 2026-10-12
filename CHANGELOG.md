# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con [SemVer](https://semver.org/lang/es/).

## [0.6.0] - 2026-10-12

### Añadido
- Integraciones por MCP: conecta servidores locales (programas) o remotos (URL) y Elissa usa sus herramientas.
  Ajustes trae listos GitHub, Jira y Confluence (servidor oficial de Atlassian) y Google Calendar, además de
  cualquier otro servidor. Lo que solo lee es libre; lo que cambia datos muestra la tarjeta de aprobación con el
  servidor, la herramienta y los datos exactos. Los tokens quedan en el Administrador de credenciales.

### Corregido
- La voz de Edge dejó de responder (403) porque Microsoft movió el servicio: ahora Elissa cambia sola al servidor
  nuevo, y si aun así falla usa la voz de Windows.

## [0.5.0] - 2026-10-11 (incluida en 0.6.0; su compilación no se publicó)

### Añadido
- Asistente de programación: ve la estructura de un proyecto, busca en el código, lee líneas numeradas y consulta git
  (estado, diferencias, historial) sin pedir permiso.
- Ejecuta comandos (pruebas, builds, lint, commits) con una tarjeta que muestra el comando exacto y la carpeta, y avisa
  si el comando publica, instala o escribe archivos.
- Con eso puede encargarse de "corre las pruebas, encuentra el error y corrígelo": edita con diferencias y vuelve a
  probar, pidiendo aprobación en cada paso.

### Seguridad
- Nunca ejecuta comandos que borran archivos o descartan trabajo (rm, del, reset duro de git, push forzado, borrar
  ramas, formatear…), aunque se los pidan.

## [0.4.0] - 2026-10-11

### Añadido
- « Hola Elissa » y « Oye Elissa » para despertarla sin tocar nada. Funciona sin internet: nada de lo que escucha sale
  de tu PC hasta que la despiertas. Se activa en Ajustes → Voz y se pausa con la pantalla bloqueada.
- Reconocimiento de voz en tu PC (whisper.cpp): privado, sin API key ni internet. Se descarga una sola vez, en versión
  rápida (60 MB) o más precisa (190 MB).
- Voces de Windows sin conexión, y respaldo automático si la voz de Edge no responde.
- Interrumpirla hablando mientras responde (opcional; mejor con audífonos).

### Corregido
- Elissa decía que el correo no estaba configurado aunque sí lo estaba: había guardado ese estado como recuerdo.
  La memoria ya no guarda estados del propio asistente, en cada turno sabe qué tiene activo de verdad y descarta
  recuerdos que copian la plantilla.

## [0.3.0] - 2026-10-11

### Añadido
- Elissa ya puede hacer cosas, siempre con una tarjeta de aprobación para lo que cambia algo:
  - Sin aprobación: abrir páginas, apps, archivos y carpetas; controlar la música y el volumen; temporizadores y
    recordatorios (con voz y notificación de Windows); lista de tareas.
  - Con aprobación: crear, editar y mover archivos (ves las diferencias antes), enviar correos (opción aparte en
    Ajustes) y usar otras ventanas: leerlas, hacer clic, escribir y presionar teclas.
- Arrastra un archivo sobre Elissa para preguntarle por él.

### Corregido
- Error 400 al hablarle justo después de una respuesta o al soltar un archivo: podían quedar dos grabaciones a la vez
  y el audio llegaba corrupto. Ahora hay una sola grabación por vez y el motor descarta audios vacíos o dañados con
  un mensaje claro.

### Seguridad
- Solo un clic en la tarjeta aprueba una acción; la voz, el atajo y el modelo no pueden. Sin ventana abierta, todo
  queda rechazado. Nunca se leen campos de contraseña ni se abren ejecutables.

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
