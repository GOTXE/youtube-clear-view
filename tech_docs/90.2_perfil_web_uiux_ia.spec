id: 90.2_perfil_web_uiux
d: perfil UI/UX web con accesibilidad y seguridad
r: [
  "cat=arch;act=require;str=strong;target=uiux.usar_estandares_universales={colores,tipografia,espaciado,componentes};impact=high",
  "cat=arch;act=require;str=strong;target=uiux.usar_estandar_web_uiux_para_comportamiento_responsive_accesibilidad;impact=high",
  "cat=arch;act=forbid;str=strong;target=uiux.colores_propios_sin_tokens;impact=high",
  "cat=arch;act=require;str=normal;target=uiux.simplicidad_claridad_responsive;impact=medium",
  "cat=sec;act=require;str=strong;target=uiux.accesibilidad_WCAG_AA;impact=high",
  "cat=sec;act=require;str=strong;target=uiux.sanitizar_html_no_trazas_csrf_no_tokens_localStorage;impact=critical",
  "cat=ia;act=require;str=normal;target=ia.consultar_estandares_antes_css_html;impact=medium",
  "cat=doc;act=require;str=normal;target=uiux.nombres_componentes_y_recursos_siguen_00.1_coding_standars;impact=medium"
]
s: [
  "componentes_web={botones,inputs,selects,cards,tablas,modales,alertas,layouts,navbars}",
  "colores_estados={--error,--success,--warning,--info}"
]
f: []
c: []
x: []
n: [
  "usar tokens de estado en lugar de colores sueltos",
  "seguridad_visual: no mostrar info interna de backend"
]
