id: estandar_codigo_limpio
d: reglas para que la IA genere código mínimo, directo y sin residuos
r: [
  "cat=arch;act=require;str=strong;target=ia.entender_problema_antes_de_escribir_codigo;impact=critical",
  "cat=arch;act=require;str=strong;target=ia.arreglar_causa_raiz_no_sintomas;impact=critical",
  "cat=arch;act=require;str=strong;target=ia.minimo_cambio_necesario_sin_codigo_extra;impact=critical",
  "cat=arch;act=forbid;str=strong;target=ia.dejar_codigo_comentado_o_muerto;impact=high",
  "cat=arch;act=forbid;str=strong;target=ia.crear_wrappers_o_helpers_para_uso_unico;impact=high",
  "cat=arch;act=forbid;str=strong;target=ia.añadir_validaciones_para_escenarios_imposibles;impact=high",
  "cat=arch;act=forbid;str=strong;target=ia.abstracciones_prematuras_sin_necesidad_real;impact=high",
  "cat=arch;act=forbid;str=normal;target=ia.shims_compatibilidad_cuando_se_puede_cambiar_directo;impact=high",
  "cat=arch;act=forbid;str=normal;target=ia.renombrar_variables_no_usadas_con_underscore_en_vez_de_borrar;impact=medium",
  "cat=arch;act=forbid;str=normal;target=ia.añadir_comentarios_tipo_removed_o_deprecated_en_vez_de_borrar;impact=medium",
  "cat=arch;act=forbid;str=normal;target=ia.try_catch_generico_sin_logica_de_recuperacion;impact=medium",
  "cat=arch;act=require;str=strong;target=ia.borrar_codigo_que_queda_sin_uso_tras_un_cambio;impact=high",
  "cat=arch;act=require;str=normal;target=ia.preferir_modificar_existente_a_crear_nuevo;impact=medium",
  "cat=arch;act=require;str=normal;target=ia.tres_lineas_similares_mejor_que_abstraccion_prematura;impact=medium",
  "cat=arch;act=require;str=normal;target=ia.un_fix_un_commit_no_mezclar_refactors_no_pedidos;impact=medium",
  "cat=arch;act=forbid;str=normal;target=ia.feature_flags_o_configurabilidad_no_solicitada;impact=medium",
  "cat=arch;act=forbid;str=normal;target=ia.docstrings_o_type_hints_en_codigo_que_no_se_toco;impact=medium",
  "cat=arch;act=require;str=strong;target=ia.si_algo_no_se_usa_se_borra_completamente;impact=high"
]
s: [
  "proceso_fix={1_leer_y_entender_contexto,2_identificar_causa_raiz,3_planear_cambio_minimo,4_implementar_solo_lo_necesario,5_verificar_que_no_queda_codigo_muerto,6_confirmar_que_el_fix_es_directo}",
  "señales_de_codigo_innecesario={wrappers_de_una_sola_llamada,funciones_helper_usadas_una_vez,variables_intermedias_sin_claridad,imports_no_usados,parametros_unused,bloques_comentados,else_imposibles}"
]
f: [
  "antes_de_escribir: leer_codigo_existente -> entender_flujo -> identificar_punto_exacto_del_problema -> cambiar_solo_eso",
  "despues_de_escribir: revisar_diff -> eliminar_residuos -> confirmar_minimalismo -> no_hay_codigo_nuevo_sin_uso"
]
c: [
  "nunca_generar_mas_de_lo_pedido",
  "nunca_refactorizar_sin_que_se_pida",
  "nunca_mejorar_codigo_adyacente_al_fix",
  "nunca_añadir_manejo_de_errores_donde_no_puede_fallar",
  "nunca_añadir_logs_o_prints_que_no_se_pidieron"
]
x: [
  "mal: crear funcion validateInput() para un solo if -> bien: poner el if directamente",
  "mal: añadir try-catch en codigo interno que no puede lanzar excepcion -> bien: confiar en el framework",
  "mal: comentar linea vieja y añadir nueva debajo -> bien: reemplazar directamente",
  "mal: crear constante para un valor usado una sola vez -> bien: usar el valor inline",
  "mal: añadir parametro opcional 'por si acaso' -> bien: añadirlo cuando se necesite",
  "mal: wrappear funcion existente en otra funcion -> bien: modificar la funcion existente",
  "mal: if (condition) { return x } else { return y } -> bien: return condition ? x : y (si es simple)"
]
n: [
  "la complejidad correcta es la minima necesaria para la tarea actual",
  "si dudas entre añadir o no añadir algo: no lo añadas",
  "el mejor codigo es el que no se escribe",
  "YAGNI: You Aren't Gonna Need It - no diseñar para requisitos hipoteticos futuros",
  "un fix debe tocar el minimo numero de archivos posible",
  "si el fix genera codigo muerto en otro sitio: borrarlo en el mismo commit"
]
