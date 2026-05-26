import streamlit as st
import xml.etree.ElementTree as ET
import io

st.set_page_config(page_title="Editor de XML - SAT", page_icon="🛠️", layout="wide")

st.title("🛠️ Modificador y Consolidador de XML de Pago")
st.write("Sube tu XML, selecciona la factura principal y descarga el XML modificado con los montos sumados y sin las referencias secundarias.")

# Espacio para subir el archivo XML
uploaded_file = st.file_uploader("Arrastra aquí tu archivo XML (REP)", type=["xml"])

if uploaded_file is not None:
    try:
        # Registrar los namespaces para que el XML conserve los prefijos 'cfdi:' y 'pago20:' al guardarse
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
        
        # Encontrar el nodo padre que contiene los documentos relacionados
        pago_node = root.find('.//pago20:Pago', ns)
        
        if pago_node is None:
            st.warning("No se encontró el nodo de Pago (Pago20) en este archivo.")
        else:
            doctos = pago_node.findall('pago20:DoctoRelacionado', ns)
            
            if not doctos:
                st.warning("No se encontraron facturas relacionadas (DoctoRelacionado) en este XML.")
            else:
                datos_facturas = []
                monto_total_xml = 0.0
                
                # Recorremos para calcular la suma y mostrar las opciones al usuario
                for i, doc in enumerate(doctos):
                    uuid = doc.get('IdDocumento', 'Sin UUID')
                    serie = doc.get('Serie', '')
                    folio = doc.get('Folio', '')
                    identificador = f"{serie}{folio}".strip() if (serie or folio) else f"Doc_{i+1}"
                    
                    imp_pagado = float(doc.get('ImpPagado', 0.0))
                    monto_total_xml += imp_pagado
                    
                    datos_facturas.append({
                        'index': i,
                        'identificador': identificador,
                        'uuid': uuid,
                        'monto_original': imp_pagado,
                        'elemento_xml': doc
                    })
                
                # Mostrar datos actuales en pantalla
                st.subheader("📝 Facturas detectadas originalmente:")
                for d in datos_facturas:
                    st.text(f"• {d['identificador']} - UUID: {d['uuid']} | Monto: ${d['monto_original']:,.2f}")
                
                st.divider()
                
                # --- PROCESO DE SELECCIÓN Y MODIFICACIÓN ---
                st.subheader("🎯 Configuración del nuevo XML")
                
                opciones_seleccion = [f"{d['identificador']} ({d['uuid'][-8:]}...)" for d in datos_facturas]
                seleccion = st.selectbox("¿Con qué factura deseas quedarte?", opciones_seleccion)
                
                idx_seleccionado = opciones_seleccion.index(seleccion)
                factura_conservar = datos_facturas[idx_seleccionado]
                
                if st.button("Generar y Procesar XML Modificado"):
                    
                    # Iterar sobre los documentos originales en el XML real
                    for doc in list(pago_node.findall('pago20:DoctoRelacionado', ns)):
                        uuid_doc = doc.get('IdDocumento')
                        
                        if uuid_doc == factura_conservar['uuid']:
                            # Si es el documento que queremos conservar, le asignamos la suma de TODOS los montos
                            # Formateamos a 2 decimales string para cumplir la regla del SAT
                            nuevo_monto_str = f"{monto_total_xml:.2f}"
                            doc.set('ImpPagado', nuevo_monto_str)
                            
                            # Opcional: Si el XML traía saldo insoluto (ImpSaldoInsoluto), lo recalculamos a 0.00 de forma lógica para control interno
                            if doc.get('ImpSaldoInsoluto'):
                                saldo_anterior = float(doc.get('ImpSaldoAnterior', 0.0))
                                nuevo_insoluto = max(0.0, saldo_anterior - monto_total_xml)
                                doc.set('ImpSaldoInsoluto', f"{nuevo_insoluto:.2f}")
                        else:
                            # Si es el del centavo o cualquier otro que no elegimos, lo ELIMINAMOS por completo del XML
                            pago_node.remove(doc)
                    
                    # Convertir el árbol XML modificado de vuelta a bytes binarios
                    xml_modificado_bytes = ET.tostring(root, encoding='utf-8', method='xml')
                    
                    st.success("¡XML reorganizado con éxito!")
                    
                    # Mostrar resumen de los cambios reflejados
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="Factura única en XML", value=factura_conservar['identificador'])
                    with col2:
                        st.metric(label="Nuevo Importe Pagado", value=f"${monto_total_xml:,.2f}")
                    
                    # Botón para descargar el nuevo archivo XML listo
                    st.download_button(
                        label="📥 Descargar XML Modificado",
                        data=xml_modificado_bytes,
                        file_name=f"MOD_{uploaded_file.name}",
                        mime="application/xml"
                    )
                    
    except Exception as e:
        st.error(f"Ocurrió un problema al transformar el XML. Detalles: '{e}'")
