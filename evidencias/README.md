# Evidencias del laboratorio 09

Capturas de la aplicación y de la consola AWS, revisadas el 14 de octubre de 2026. Las capturas de AWS se recortaron para excluir la barra de cuenta y conservar el recurso y la configuración relevantes. No se incluyen claves de acceso ni URLs prefirmadas.

| Captura | Qué demuestra |
| --- | --- |
| [01 Galería](evidencia1.png) | Una imagen JPG aparece en la galería con el mensaje «Imagen subida y validada». |
| [02 Prefijos S3](02-s3-prefijos.jpg) | El bucket contiene `originales/`, `miniaturas/` y `temporal/`. |
| [03 Imágenes S3](03-s3-imagenes.jpg) | Los objetos de prueba están almacenados en `originales/`. |
| [04 Tres versiones](04-s3-tres-versiones.jpg) | `versionado-demo.png` conserva tres versiones con identificadores distintos después de la restauración. |
| [05 Versionado habilitado](05-s3-versionado-habilitado.jpg) | Región `us-east-1`, ARN del bucket y control de versiones habilitado. |
| [06 Cifrado SSE-S3](06-s3-cifrado-sse-s3.jpg) | El cifrado predeterminado usa claves administradas por Amazon S3. |
| [07 Bloqueo público](07-s3-bloqueo-publico.jpg) | «Bloquear todo el acceso público» está activado. |
| [08 Política HTTPS](08-s3-politica-https.jpg) | La política deniega solicitudes con `aws:SecureTransport=false`. |
| [09 CORS](09-s3-cors.jpg) | Se permiten GET y PUT desde los dos orígenes locales de la aplicación. |
| [10 Regla lifecycle](10-lifecycle-regla-habilitada.jpg) | `regla-imagenes-antiguas` está habilitada y filtrada por `originales/`. |
| [11 Transiciones lifecycle](11-lifecycle-transiciones.jpg) | Standard-IA a 30 días, Glacier Instant Retrieval a 90, versiones antiguas a Deep Archive a 60 y expiración a 365; eliminación de marcadores vencidos configurada. |
| [12 Política IAM](12-iam-permisos-minimos.jpg) | La política inline de `app-imagenes-user` permite listar el bucket y operar sobre sus objetos. |
| [13 Recursos IAM](13-iam-permisos-objetos.jpg) | GetObject, PutObject y DeleteObject se limitan a los objetos del bucket del laboratorio. |

Estas capturas muestran el estado de la configuración al momento de la revisión. Las transiciones de lifecycle se ejecutarán cuando se cumplan sus plazos; no evidencian una transición ya realizada. La captura de las tres versiones corresponde al estado posterior a restaurar el objeto: no muestra el marcador de eliminación que se retiró durante la prueba previa. Las pruebas por CLI y API se describen en el README principal.
