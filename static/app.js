const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED = new Set(['image/jpeg', 'image/png', 'image/webp']);
const status = document.querySelector('#status');
const gallery = document.querySelector('#gallery');

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Error HTTP ${response.status}`);
  return data;
}

async function loadGallery() {
  gallery.replaceChildren();
  const images = await jsonRequest('/api/images');
  if (!images.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Aún no hay imágenes. Sube la primera para comenzar.';
    gallery.append(empty);
    return;
  }
  for (const item of images) {
    const card = document.createElement('article');
    card.className = 'card';
    const img = document.createElement('img');
    img.src = item.url;
    img.alt = item.key.split('/').at(-1);
    img.loading = 'lazy';
    const details = document.createElement('div');
    details.className = 'card-body';
    const name = document.createElement('span');
    name.textContent = item.key.split('/').at(-1);
    const download = document.createElement('a');
    download.href = item.url;
    download.textContent = 'Ver o descargar';
    download.target = '_blank';
    download.rel = 'noopener noreferrer';
    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'danger';
    del.textContent = 'Eliminar';
    del.addEventListener('click', async () => {
      if (!confirm(`¿Eliminar ${name.textContent}?`)) return;
      try {
        await jsonRequest(`/api/images/${encodeURIComponent(item.key)}`, {method: 'DELETE'});
        status.textContent = 'Imagen eliminada.';
        await loadGallery();
      } catch (error) { status.textContent = error.message; }
    });
    details.append(name, download, del);
    card.append(img, details);
    gallery.append(card);
  }
}

document.querySelector('#upload-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = document.querySelector('#file').files[0];
  if (!file) return;
  if (!ALLOWED.has(file.type)) { status.textContent = 'Tipo no permitido. Usa JPG, PNG o WebP.'; return; }
  if (file.size < 1 || file.size >= MAX_BYTES) { status.textContent = 'El archivo debe ser menor de 5 MB.'; return; }
  status.textContent = 'Generando enlace temporal…';
  try {
    const signed = await jsonRequest('/api/upload-url', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filename: file.name, contentType: file.type, sizeBytes: file.size})
    });
    status.textContent = 'Subiendo directamente a S3…';
    const put = await fetch(signed.uploadUrl, {
      method: 'PUT', headers: {'Content-Type': file.type, 'x-amz-server-side-encryption': 'AES256'}, body: file
    });
    if (!put.ok) throw new Error(`S3 rechazó la carga (${put.status}).`);
    status.textContent = 'Verificando el contenido…';
    await jsonRequest('/api/images/verify', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: signed.key})
    });
    status.textContent = 'Imagen subida y validada.';
    event.target.reset();
    await loadGallery();
  } catch (error) { status.textContent = error.message; }
});

document.querySelector('#refresh').addEventListener('click', () => loadGallery().catch(error => status.textContent = error.message));
loadGallery().catch(error => status.textContent = error.message);
