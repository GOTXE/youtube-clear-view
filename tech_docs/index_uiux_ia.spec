id: index_uiux
d: índice maestro de estándares UX/UI por plataforma
r: [
  "cat=arch;act=require;str=strong;target=uiux.aplicar_universales_siempre;impact=high",
  "cat=arch;act=require;str=strong;target=uiux.cargar_estandar_plataforma_segun_tipo;impact=high",
  "cat=arch;act=recommend;str=normal;target=uiux.contextos_adicionales_según_necesidad;impact=medium"
]
s: [
  "universales={estandar_colores,estandar_tipografia,estandar_espaciado,estandar_componentes_basicos}",
  "plataformas={web:{estandar_web_uiux,90.2_perfil_web_uiux},escritorio:{estandar_escritorio_uiux,90.3_perfil_escritorio_uiux},movil:{estandar_movil_uiux,90.4_perfil_movil_uiux},embebidos:{estandar_embebidos_uiux,90.5_perfil_embebidos_uiux},juegos_hud:{estandar_juegos_hud_uiux,90.6_perfil_juegos_hud_uiux},dashboards:{estandar_dashboards_uiux,90.7_perfil_dashboards_uiux}}"
]
f: [
  "generar_UI: cargar_universales -> detectar_plataforma -> cargar_estandar_plataforma -> aplicar_reglas -> generar_UI_coherente"
]
c: []
x: []
n: [
  "jerarquia: universales > plataforma > contextuales"
]
