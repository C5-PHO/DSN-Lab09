# Lab 09 · Galería privada de imágenes en Amazon S3

Aplicación Flask + boto3 para cargar, listar, visualizar y eliminar imágenes de un bucket privado mediante URLs prefirmadas. El navegador sube el archivo directamente a S3; el backend nunca entrega credenciales AWS. El código cubre el ejercicio 4 y `infra/` contiene las configuraciones de los ejercicios 2 y 3. Los ejercicios de consola y AWS CLI se documentan abajo para ejecutarlos en una cuenta autorizada.

> **Estado:** la lógica local y la integración con un bucket privado de S3 se verificaron el 14 de octubre de 2026. Los recursos de AWS son temporales y pueden generar cargos. No se incluyen credenciales ni el informe personal en este repositorio.

## Requisitos

- Python 3.10+ y AWS CLI configurado con un perfil propio (o IAM Role si se despliega en EC2).
- Cuenta AWS autorizada para S3 e IAM.
- Bucket privado en `us-east-1` (o ajustar `AWS_REGION`).

## 1. Crear el bucket y probar S3

En la consola S3, crea un nombre globalmente único como `lab-09-farfan-20261014-<sufijo>` en `us-east-1`. Mantén **Block all public access** habilitado y **ACLs desactivadas**. Crea los prefijos `originales/`, `miniaturas/` y `temporal/`; sube tres imágenes de prueba JPG/PNG menores de 5 MB a `originales/`.

Con un perfil administrativo de laboratorio y reemplazando `BUCKET_NAME` por el nombre real:

```bash
aws s3 ls --profile lab-admin
aws s3 ls s3://BUCKET_NAME/originales/ --profile lab-admin
aws s3 cp ./mi-foto.jpg s3://BUCKET_NAME/originales/ --profile lab-admin
aws s3 cp s3://BUCKET_NAME/originales/mi-foto.jpg ./descarga.jpg --profile lab-admin
aws s3 sync ./fotos/ s3://BUCKET_NAME/originales/ --profile lab-admin
```

La URL pública de un objeto privado debe responder `403 AccessDenied`; el ARN `arn:aws:s3:::BUCKET_NAME` identifica el recurso para políticas, no es una URL de descarga.

## 2. IAM, HTTPS y cifrado

En IAM crea `app-imagenes-user` **sin acceso a consola**, sin grupo, con una política personalizada basada en [`infra/iam-policy.template.json`](infra/iam-policy.template.json). Sustituye `BUCKET_NAME` en los dos ARN antes de adjuntarla. Crea una sola Access Key para el ejercicio y guárdala únicamente en un perfil local `app-user` (`aws configure --profile app-user`). No la pegues en `.env`, código, capturas ni Git.

En la pestaña Permissions del bucket, aplica [`infra/bucket-policy.template.json`](infra/bucket-policy.template.json), también con el nombre real. En Properties selecciona cifrado predeterminado **SSE-S3 (AES-256)**. Comprueba en un objeto nuevo que figura como cifrado. En Permissions > CORS aplica [`infra/cors.json`](infra/cors.json), cambiando los orígenes si usas otro host/puerto.

```bash
aws s3 ls s3://BUCKET_NAME/ --profile app-user
aws s3 cp ./test.jpg s3://BUCKET_NAME/originales/ --profile app-user
aws s3api delete-bucket --bucket BUCKET_NAME --profile app-user
```

Los dos primeros comandos deben funcionar; el último debe devolver `AccessDenied` **sin borrar el bucket**. No uses el usuario de aplicación para cambios de políticas, versionado o lifecycle.

## 3. Versionado y lifecycle

Habilita versionado en Properties. Sube tres veces el mismo nombre de imagen con contenidos distintos, activa **Show versions**, elimínala sin `versionId` y observa el *delete marker*. Para restaurarla, elimina **solo ese delete marker** desde la vista de versiones. Configura la regla de [`infra/lifecycle.json`](infra/lifecycle.json) en Management > Lifecycle rules: `originales/` pasa a Standard-IA a los 30 días y Glacier Instant Retrieval a los 90; las versiones antiguas pasan a Deep Archive a los 60 días y expiran a los 365 días.

**Advertencia de costo:** esa regla afecta a **todos** los objetos de `originales/`, incluso los que se consultan a menudo. Para producción, separa los objetos fríos mediante otro prefijo o etiquetas y calcula también costos de recuperación, solicitudes, versiones y permanencia mínima.

## 4. Ejecutar la galería

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edita `.env`: pon el nombre real en `S3_BUCKET`, la región y el nombre de tu perfil `AWS_PROFILE`. En un despliegue EC2 con IAM Role, elimina `AWS_PROFILE` y usa el rol de instancia. Luego:

```bash
.venv/bin/python app.py
```

Abre `http://127.0.0.1:3000`. Esta aplicación escucha solo en localhost y **no implementa autenticación de usuarios**; no la expongas públicamente sin autenticarla, limitar la tasa y añadir controles de producción.

Flujo de carga: `POST /api/upload-url` valida nombre, MIME y tamaño declarado y emite una URL PUT de 5 minutos hacia `temporal/`. El navegador hace PUT directo a S3 con `Content-Type` y `x-amz-server-side-encryption: AES256`. Después llama a `POST /api/images/verify`: el backend comprueba tamaño real y *magic bytes*, copia el archivo válido a `originales/` y elimina el temporal. `GET /api/images` entrega URLs GET de 15 minutos; `DELETE /api/images/<key>` elimina una imagen de `originales/`. La carpeta temporal evita que una carga sin verificar aparezca en la galería; debes limpiar archivos temporales abandonados en un entorno real.

## Pruebas

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

La suite cubre la emisión de URL de 5 minutos, rechazo de PDF y 10 MB, validación posterior del contenido, listado con URL de 15 minutos y restricción del borrado. Para la evidencia real de AWS, comprueba además en el navegador:

1. Un JPG válido aparece en la galería.
2. Un PDF o EXE se bloquea antes de solicitar una URL.
3. Una petición manual de 10 MB a `/api/upload-url` devuelve HTTP 400.
4. Una URL GET copiada deja de servir después de 16 minutos (no se puede acelerar esta prueba local).
5. El código fuente y las solicitudes de red no muestran Access Keys; el PUT del archivo va al endpoint de S3, no al backend.
6. La consola AWS muestra Block Public Access, SSE-S3, versionado, política HTTPS y regla lifecycle.

La captura de la aplicación está en [`evidencias/evidencia1.png`](evidencias/evidencia1.png): muestra una imagen JPG cargada y validada en la galería privada. No contiene credenciales ni URLs prefirmadas visibles. Esta captura no sustituye la demostración de permisos, versionado y ciclo de vida en la consola de AWS. Las respuestas de análisis y el video del laboratorio pertenecen al informe personal, no al repositorio público.

## Validación real en AWS (14 de octubre de 2026)

Se creó un bucket privado en `us-east-1` con los tres prefijos, bloqueo total de acceso público, cifrado SSE-S3, versionado y una política que rechaza conexiones HTTP. La regla de ciclo de vida para `originales/` quedó habilitada con transiciones a Standard-IA (30 días) y Glacier Instant Retrieval (90 días), y tratamiento de versiones no actuales. Su **ejecución futura** no se puede demostrar el mismo día de creación.

- Tres PNG de prueba se cargaron y aparecieron en la galería. El objeto inspeccionado reportó `ServerSideEncryption: AES256`.
- El flujo completo `POST /api/upload-url` → PUT prefirmado a S3 → `POST /api/images/verify` → listado → borrado respondió `200`, `200`, `201`, listado correcto y `200`, respectivamente.
- La comprobación CORS desde `http://127.0.0.1:3000` respondió `200` y permitió `GET, PUT`; la URL pública sin firma devolvió `403`.
- Un PDF y una petición de 10 MB fueron rechazados con `400`; una URL de prueba con vencimiento de un segundo devolvió `403` tras caducar. Las URLs emitidas por la aplicación duran 5 minutos (PUT) y 15 minutos (GET), según las pruebas automatizadas.
- El usuario IAM limitado pudo listar y cargar objetos, pero `DeleteBucket` y `ListBucketVersions` devolvieron `AccessDenied`.
- Se crearon tres versiones del mismo objeto, se comprobó el *delete marker* y se restauró la versión más reciente eliminando únicamente ese marcador. Las tres versiones de contenido permanecieron intactas.
- La suite automatizada terminó con **9 pruebas aprobadas**.

## Limpieza al terminar

S3 **no se apaga** como una instancia EC2: mientras queden objetos, versiones o solicitudes, puede haber cargos. Cuando ya no necesites la demostración, elimina todas las versiones y delete markers, vacía y borra el bucket, desactiva/elimina la Access Key y elimina el usuario IAM. Hazlo solo después de conservar las evidencias y confirmar que no necesitas los objetos.
