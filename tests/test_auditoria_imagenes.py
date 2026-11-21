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
