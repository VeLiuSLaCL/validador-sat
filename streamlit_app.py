import streamlit as st
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Editor de XML - SAT", page_icon="🛠️", layout="wide")

st.title("🛠️ Consolidador Avanzado de XML de Pago (CFDI 4.0)")
st.write("Sube tu XML, selecciona la factura principal y genera el archivo limpio con saldos, pagos e impuestos (Base e Importe) totalmente sumados.")

# Espacio para subir el archivo XML
uploaded_file = st.file_uploader("Arrastra aquí tu archivo XML (REP)", type=["xml"])

if uploaded_file is not None:
    try:
        # Registrar los namespaces para conservar los prefijos oficiales
        ET.register_namespace('cfdi', 'http://www.sat.gob.mx/cfdv/4')
        ET.register_namespace('pago20', 'http://www.sat.gob.mx/Pagos20')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

        # Leer y parsear el XML
        xml_data = uploaded_file.read()
        root = ET.fromstring(xml_data)
        
        ns = {
            'cfdi': 'http://www.sat.gob.mx/cfdv/4',
            'pago20': 'http://www.sat.gob.mx/Pagos20'
        }
        
        # Encontrar el nodo padre de los pagos
        pago_node = root.find('.//pago20:Pago', ns)
        
        if pago_node is None:
            st.warning("No se encontró el nodo de Pago (pago20:Pago) en este archivo.")
        else:
            doctos = pago_node.findall('pago20:DoctoRelacionado', ns)
            
            if not doctos:
                st.warning("No se encontraron facturas relacionadas (DoctoRelacionado) en este XML.")
            else:
                datos_facturas = []
                
                # Totales globales que acumularemos de TODOS los documentos relacionados
                total_imp_saldo_ant = 0.0
                total_imp_pagado = 0.0
                total_base_dr = 0.0
                total_importe_dr = 0.0
                
                # Primera pasada: Extraer datos y acumular todas las sumas
                for i, doc in enumerate(doctos):
                    uuid = doc.get('IdDocumento', 'Sin UUID')
                    serie = doc.get('Serie', '')
                    folio = doc.get('Folio', '')
                    identificador = f"{serie}{folio}".strip() if (serie or folio) else f"Doc_{i+1}"
                    
                    # Capturar atributos del documento
                    imp_saldo_ant = float(doc.get('ImpSaldoAnterior', 0.0))
                    imp_pagado = float(doc.get('ImpPagado', 0.0))
                    
                    total_imp_saldo_ant += imp_saldo_ant
                    total_imp_pagado += imp_pagado
                    
                    # Buscar BaseDR e ImporteDR dentro de los impuestos del documento relacionado
                    # Estructura: DoctoRelacionado -> ImpuestosDR -> TrasladosDR -> TrasladoDR
                    traslados = doc.findall('.//pago20:TrasladoDR', ns)
                    for tras in traslados:
                        base_dr = float(tras.get('BaseDR', 0.0))
                        importe_dr = float(tras.get('ImporteDR', 0.0))
                        total_base_dr += base_dr
                        total_importe_dr += importe_dr
                    
                    datos_facturas.append({
                        'identificador': identificador,
                        'uuid': uuid,
                        'monto_original': imp_pagado
                    })
                
                # Mostrar lo detectado originalmente en una lista limpia
                st.subheader("📝 Facturas detectadas originalmente:")
                for d in datos_facturas:
                    st.text(f"• {d['identificador']} - UUID: {d['uuid']} | Pago Original: ${d['monto_original']:,.2f}")
                
                st.divider()
                
                # --- PROCESO DE SELECCIÓN ---
                st.subheader("🎯 Configuración del nuevo XML")
                
                opciones_seleccion = [f"{d['identificador']} ({d['uuid'][-8:]}...)" for d in datos_facturas]
                seleccion = st.selectbox("¿Con qué factura deseas quedarte para acumular los saldos?", opciones_seleccion)
                
                idx_seleccionado = opciones_seleccion.index(seleccion)
                factura_conservar = datos_facturas[idx_seleccionado]
                
                if st.button("Generar y Procesar XML Modificado"):
                    
                    # Segunda pasada: Modificar el XML real
                    for doc in list(pago_node.findall('pago20:DoctoRelacionado', ns)):
                        uuid_doc = doc.get('IdDocumento')
                        
                        if uuid_doc == factura_conservar['uuid']:
                            # Recalcular saldos principales del documento elegido
                            nuevo_saldo_insoluto = max(0.0, total_imp_saldo_ant - total_imp_pagado)
                            
                            doc.set('ImpSaldoAnterior', f"{total_imp_saldo_ant:.2f}")
                            doc.set('ImpPagado', f"{total_imp_pagado:.2f}")
                            doc.set('ImpSaldoInsoluto', f"{nuevo_saldo_insoluto:.2f}")
                            
                            # Recalcular Base e Importe dentro de los subnodos de impuestos de esta factura
                            traslados = doc.findall('.//pago20:TrasladoDR', ns)
                            for tras in traslados:
                                tras.set('BaseDR', f"{total_base_dr:.2f}")
                                tras.set('ImporteDR', f"{total_importe_dr:.2f}")
                        else:
                            # Si es la factura del ajuste o la que no elegiste, se REMUEVE por completo del XML
                            pago_node.remove(doc)
                    
                    # Re-calcular el monto global en el encabezado del Pago si fuera necesario (pago20:Pago Monto)
                    pago_node.set('Monto', f"{total_imp_pagado:.2f}")
                    
                    # Convertir el árbol XML modificado de vuelta a formato de archivo
                    xml_modificado_bytes = ET.tostring(root, encoding='utf-8', method='xml')
                    
                    st.success("¡XML modificado e importes consolidados correctamente!")
                    
                    # Resumen visual del resultado de las sumas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(label="Factura Conservada", value=factura_conservar['identificador'])
                        st.metric(label="Suma ImpSaldoAnterior", value=f"${total_imp_saldo_ant:,.2f}")
                    with col2:
                        st.metric(label="Suma Total ImpPagado", value=f"${total_imp_pagado:,.2f}")
                        st.metric(label="Suma Total BaseDR", value=f"${total_base_dr:,.2f}")
                    with col3:
                        st.metric(label="Nuevo ImpSaldoInsoluto", value=f"${max(0.0, total_imp_saldo_ant - total_imp_pagado):,.2f}")
                        st.metric(label="Suma Total ImporteDR (IVA)", value=f"${total_importe_dr:,.2f}")
                    
                    # Descarga del archivo XML corregido
                    st.download_button(
                        label="📥 Descargar XML Modificado",
                        data=xml_modificado_bytes,
                        file_name=f"CONSOLIDADO_{uploaded_file.name}",
                        mime="application/xml"
                    )
                    
    except Exception as e:
        st.error(f"Ocurrió un problema al transformar los nodos del XML. Detalles: '{e}'")
