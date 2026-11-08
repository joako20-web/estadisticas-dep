"""uso:
  python -m datosdep generar dh_masc [--grupo A] [--jornada 2]   # imágenes en out/
  python -m datosdep semana [--reintento]                        # carruseles -> Telegram
  python -m datosdep bot [--minutos 14]                          # escucha Telegram
  python -m datosdep video dh_masc [--jornada 2]                 # reel con motion graphics (out/*.mp4)
  python -m datosdep video dh_masc --tipo final --jornada 2 --partido 17648   # "así fue" de un partido
  python -m datosdep video dh_masc --jornada 2 [--tipo xv|mvp] # otras plantillas
  python -m datosdep descubrir [--temporada 2627]                # ligas disponibles en el origen A
"""
import argparse
import os
import sys

from datosdep.pipeline import preparar_jornada
from datosdep.render.render import renderizar_jornada


def main() -> None:
    ap = argparse.ArgumentParser(prog="datosdep")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar", help="descarga datos de una jornada y genera las imágenes")
    g.add_argument("competicion")
    g.add_argument("--grupo", default="unico")
    g.add_argument("--jornada", type=int, help="por defecto, la última jugada")
    g.add_argument("--sin-imagenes", action="store_true")
    s = sub.add_parser("semana", help="manda a Telegram el carrusel de la última jornada de cada liga")
    s.add_argument("--reintento", action="store_true", help="solo reenvía los que tenían actas incompletas")
    d = sub.add_parser("descubrir", help="lista las ligas publicadas en el origen A (para añadirlas a config)")
    d.add_argument("--temporada", type=int, default=2627, help="p. ej. 2627 = 2026/27")
    v = sub.add_parser("video", help="reel de resultados de una jornada (necesita Node y video/)")
    v.add_argument("competicion")
    v.add_argument("--grupo", default="unico")
    v.add_argument("--jornada", type=int, help="por defecto, la última jugada")
    v.add_argument("--tipo", default="jornada", help="plantilla (ver datosdep/videos/__init__.py)")
    v.add_argument("--partido", type=int, help="id del partido (plantillas por partido, p. ej. --tipo final)")
    b = sub.add_parser("bot", help="escucha Telegram durante unos minutos")
    b.add_argument("--minutos", type=float, default=14)
    args = ap.parse_args()

    if args.cmd == "generar":
        ruta = preparar_jornada(args.competicion, args.grupo, args.jornada)
        print(f"datos: {ruta}")
        if not args.sin_imagenes:
            for img in renderizar_jornada(ruta):
                print(f"  {img}")
        return

    if args.cmd == "video":
        from datosdep.videos import reel

        extra = {"id_partido": args.partido} if args.partido else {}
        print(reel(args.competicion, args.grupo, args.jornada, tipo=args.tipo, **extra))
        return
    if args.cmd == "descubrir":
        from datosdep.scraper.origen_a import compartido

        for x in compartido().descubrir(args.temporada):
            print(f"{x['id_grupo']:>6}  {x['territorial'][:28]:28}  {x['competicion'][:40]:40}  {x['fase']} / {x['grupo']}")
        return

    from datosdep import estado, flujo
    from datosdep.telegram import Telegram

    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("Falta la variable TELEGRAM_TOKEN")
    tg = Telegram(token)
    if args.cmd == "semana":
        chat_id = estado.bot().get("chat_id")
        if not chat_id:
            sys.exit("El bot aún no está vinculado: escríbele /start en Telegram")
        print("enviados:", flujo.semana(tg, chat_id, args.reintento))
    elif args.cmd == "bot":
        flujo.bucle(tg, args.minutos)


if __name__ == "__main__":
    main()
