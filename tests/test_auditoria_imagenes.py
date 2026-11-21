"""La auditoría de imágenes detecta texto cortado, fuera de la imagen, con poco margen y solapado."""
from datosdep.render import render

HTML = """<html><body style="margin:0"><section class="slide" style="position:relative;width:1080px;height:1350px;font:40px sans-serif">
<div id="ok" style="position:absolute;left:100px;top:100px">Texto bien colocado</div>
<div id="margen" style="position:absolute;left:10px;top:300px">Pegado al borde izquierdo</div>
<div id="fuera" style="position:absolute;left:900px;top:400px;white-space:nowrap">Se sale por la derecha del todo</div>
<div id="corta" style="position:absolute;left:100px;top:500px;width:150px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">Nombre larguísimo recortado</div>
<div style="position:absolute;left:100px;top:700px">Encima uno</div>
<div style="position:absolute;left:110px;top:705px">Encima otro</div>
<div style="position:absolute;left:100px;top:900px;font-size:300px;line-height:1.2">9</div>
<div style="position:absolute;left:100px;top:1250px;font-size:24px">etiqueta bajo el número</div>
</section></body></html>"""


def test_detecta_los_cuatro_problemas_y_no_da_falsos_positivos():
    pagina = render._NAV.pagina(1080, 1350)
    try:
        pagina.set_content(HTML)
        problemas = pagina.evaluate(render._JS_AUDITA, 40)
    finally:
        pagina.close()
    tipos = {(p["tipo"], p["texto"][:12]) for p in problemas}
    assert ("margen", "Pegado al bo") in tipos
    assert ("fuera", "Se sale por ") in tipos
    assert ("corta", "Nombre largu") in tipos
    assert any(p["tipo"] == "solapa" and p["texto"].startswith("Encima") for p in problemas)
    assert not any(p["texto"] == "Texto bien colocado" for p in problemas)
    assert not any(p["texto"].startswith("etiqueta") for p in problemas)  # junto a un número enorme pero sin tocarlo


HTML2 = """<html><body style="margin:0"><section class="slide" style="position:relative;width:1080px;height:1350px;font:40px sans-serif">
<div style="position:absolute;left:100px;top:100px;width:600px;background:#f5c518;color:#000">
  <div style="text-align:right">PTS pegado</div></div>
<div style="position:absolute;left:100px;top:300px;width:600px;background:#f5c518;color:#000">
  <div style="text-align:right;padding-right:30px">PTS con aire</div></div>
<div style="position:absolute;left:100px;top:500px;white-space:nowrap"><span style="display:inline-block">NOMBRE LARGO</span><span style="display:inline-block;margin-left:6px">6</span></div>
<div style="position:absolute;left:100px;top:600px;white-space:nowrap"><span style="display:inline-block">NOMBRE</span><span style="display:inline-block;margin-left:60px">6</span></div>
</section></body></html>"""


def test_detecta_texto_pegado_al_borde_de_su_caja_y_al_vecino():
    pagina = render._NAV.pagina(1080, 1350)
    try:
        pagina.set_content(HTML2)
        problemas = pagina.evaluate(render._JS_AUDITA, 40)
    finally:
        pagina.close()
    assert any(p["tipo"] == "pegado" and p["texto"] == "PTS pegado" for p in problemas)
    assert not any(p["tipo"] == "pegado" and p["texto"] == "PTS con aire" for p in problemas)
    assert any(p["tipo"] == "junto" and "NOMBRE LARGO" in (p["texto"], p["con"]) for p in problemas)
    assert not any(p["tipo"] == "junto" and p["texto"] == "NOMBRE" for p in problemas)
