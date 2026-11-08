#!/usr/bin/env bash
# Guarda y recupera los ficheros privados dentro de paquete.bin (cifrado con PAQUETE_CLAVE).
#   abrir  -> descifra y extrae (si no hay paquete, no hace nada)
#   cerrar -> vuelve a empaquetar; solo escribe si el contenido ha cambiado
set -euo pipefail
cd "$(dirname "$0")/.."
LISTA=(estado assets/logo_original.png config/marca.yaml config/publicacion.yaml data/fotos)
: "${PAQUETE_CLAVE:?falta PAQUETE_CLAVE}"

empaquetar() {
  local presentes=()
  for f in "${LISTA[@]}"; do [ -e "$f" ] && presentes+=("$f"); done
  tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf - "${presentes[@]}" | gzip -n -9
}

case "${1:-}" in
  abrir)
    [ -f paquete.bin ] || exit 0
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:PAQUETE_CLAVE -in paquete.bin | tar -xzf -
    ;;
  cerrar)
    nuevo=$(empaquetar | sha256sum | cut -d' ' -f1)
    if [ -f paquete.sha ] && [ "$(cat paquete.sha)" = "$nuevo" ]; then exit 0; fi
    empaquetar | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:PAQUETE_CLAVE -out paquete.bin
    echo "$nuevo" > paquete.sha
    ;;
  *) echo "uso: $0 abrir|cerrar" >&2; exit 2 ;;
esac
