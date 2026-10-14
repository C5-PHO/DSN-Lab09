"""Private S3 image gallery for Lab 09."""

import os
import re
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

ALLOWED_TYPES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}
MAX_BYTES = 5 * 1024 * 1024
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def create_app(s3=None):
    app = Flask(__name__)
    app.config["S3_BUCKET"] = os.getenv("S3_BUCKET", "")
    app.config["S3_CLIENT"] = s3 or boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

    def client():
        return app.config["S3_CLIENT"]

    def bucket():
        value = app.config["S3_BUCKET"]
        if not value:
            raise ValueError("S3_BUCKET no está configurado")
        return value

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/upload-url")
    def upload_url():
        body = request.get_json(silent=True) or {}
        filename = body.get("filename")
        content_type = body.get("contentType")
        size = body.get("sizeBytes")
        if not isinstance(filename, str) or not filename or len(filename) > 180:
            return jsonify(error="Nombre de archivo inválido"), 400
        if content_type not in ALLOWED_TYPES:
            return jsonify(error="Tipo de archivo no permitido"), 400
        if type(size) is not int or size < 1 or size >= MAX_BYTES:
            return jsonify(error="El archivo debe ser menor de 5 MB"), 400
        safe_name = SAFE_NAME.sub("_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).lstrip(".")
        if not safe_name:
            return jsonify(error="Nombre de archivo inválido"), 400
        key = f"temporal/{uuid.uuid4().hex}-{safe_name}"
        try:
            url = client().generate_presigned_url(
                "put_object",
                Params={"Bucket": bucket(), "Key": key, "ContentType": content_type, "ServerSideEncryption": "AES256"},
                ExpiresIn=300,
                HttpMethod="PUT",
            )
            return jsonify(uploadUrl=url, key=key, expiresIn=300)
        except (BotoCoreError, ClientError, ValueError) as exc:
            app.logger.error("No se pudo emitir URL de carga: %s", exc)
            return jsonify(error="No se pudo generar la URL"), 503

    @app.post("/api/images/verify")
    def verify_upload():
        body = request.get_json(silent=True) or {}
        key = body.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"temporal/[a-f0-9]{32}-[A-Za-z0-9._-]+", key):
            return jsonify(error="Clave temporal inválida"), 400
        try:
            metadata = client().head_object(Bucket=bucket(), Key=key)
            size = metadata["ContentLength"]
            content_type = metadata.get("ContentType", "")
            valid = content_type in ALLOWED_TYPES and 0 < size < MAX_BYTES
            if valid:
                response = client().get_object(Bucket=bucket(), Key=key, Range="bytes=0-11")
                prefix = response["Body"].read(12)
                valid = any(prefix.startswith(magic) for magic in ALLOWED_TYPES[content_type])
                if content_type == "image/webp":
                    valid = valid and prefix[8:12] == b"WEBP"
            if not valid:
                client().delete_object(Bucket=bucket(), Key=key)
                return jsonify(error="El archivo no supera la validación del servidor"), 400
            final_key = "originales/" + key.removeprefix("temporal/")
            client().copy_object(
                Bucket=bucket(), Key=final_key,
                CopySource={"Bucket": bucket(), "Key": key},
                ContentType=content_type, MetadataDirective="REPLACE", ServerSideEncryption="AES256",
            )
            client().delete_object(Bucket=bucket(), Key=key)
            return jsonify(key=final_key), 201
        except (BotoCoreError, ClientError, ValueError, KeyError) as exc:
            app.logger.error("No se pudo verificar carga: %s", exc)
            return jsonify(error="No se pudo validar la carga"), 503

    @app.get("/api/images")
    def list_images():
        try:
            objects = client().get_paginator("list_objects_v2").paginate(Bucket=bucket(), Prefix="originales/")
            items = []
            for page in objects:
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/"):
                        continue
                    url = client().generate_presigned_url(
                        "get_object", Params={"Bucket": bucket(), "Key": obj["Key"]}, ExpiresIn=900
                    )
                    items.append({"key": obj["Key"], "size": obj["Size"], "lastModified": obj["LastModified"].isoformat(), "url": url})
            return jsonify(items)
        except (BotoCoreError, ClientError, ValueError) as exc:
            app.logger.error("No se pudo listar imágenes: %s", exc)
            return jsonify(error="No se pudo listar las imágenes"), 503

    @app.delete("/api/images/<path:key>")
    def delete_image(key):
        if not key.startswith("originales/") or key == "originales/" or ".." in key:
            return jsonify(error="Clave inválida"), 400
        try:
            client().delete_object(Bucket=bucket(), Key=key)
            return jsonify(deleted=True)
        except (BotoCoreError, ClientError, ValueError) as exc:
            app.logger.error("No se pudo eliminar imagen: %s", exc)
            return jsonify(error="No se pudo eliminar la imagen"), 503

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "3000")), debug=False)
