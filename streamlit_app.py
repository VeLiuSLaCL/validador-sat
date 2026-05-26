import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="Control de Pagos SAT", page_icon="📊", layout="wide")

st.title("📊 Optimizador de Complementos de Pago SAT")
st.write("Sube tu archivo XML para consolidar los montos de múltiples facturas relacionadas.")

# Espacio para subir el archivo XML
uploaded_file = st.file_uploader("Arrastra aquí tu archivo XML (REP)", type=["xml"])

if uploaded_file is not None:
    try:
        # Leer y parsear el XML
        xml_data = uploaded_file.read()
        root = ET.fromstring(xml_data)
        
        # El SAT usa 'namespaces' en el XML, definimos los más comunes para CFDI 4.0 y Pago 2.0
        ns = {
            'cfdi': 'http://www.sat.gob.mx/cfdv/4',
            'pago20': 'http://www.sat.gob.mx/Pagos20'
        }
        
        # Buscar todos los documentos relacionados
        doctos = root.findall('.//pago20:DoctoRelacionado', ns)
        
        if not doctos:
            st.warning("No se encontraron nodos 'DoctoRelacionado' (CFDI 4.0) en este archivo.")
        else:
            datos_facturas = []
            monto_total_xml = 0.0
            
            # Extraer la información de cada factura relacionada
            for i, doc in enumerate(doctos):
                uuid = doc.get('IdDocumento', 'Sin UUID')
                serie = doc.get('Serie', '')
                folio = doc.get('Folio', '')
                identificador = f"{serie}{folio}".strip() if (serie or folio) else f"Doc_{i+1}"
                
                # Importe pagado a esta factura
                imp_pagado = float(doc.get('ImpPagado', 0.0))
                monto_total_xml += imp_pagado
                
                datos_facturas.append({
                    'ID Interno': identificador,
                    'UUID (Folio Fiscal)': uuid,
                    'Monto Relacionado': imp_pagado
                })
            
            # Convertir a tabla para mostrar al usuario
            df = pd.DataFrame(datos_facturas)
            
            st.subheader("📝 Facturas detectadas en el XML")
            st.dataframe(df, use_container_width=True)
            
            st.divider()
            
            # --- AQUÍ SUCEDE TU MAGIA ---
            st.subheader("🎯 Consolidación Personalizada")
            st.write("Selecciona la factura con la que te deseas quedar para tu control interno. El sistema le sumará automáticamente los montos de las demás.")
            
            # El usuario elige con qué identificador/UUID quedarse
            opciones_seleccion = [f"{d['ID Interno']} ({d['UUID'][-8:]}...)" for d in datos_facturas]
            seleccion = st.selectbox("Conservar factura:", opciones_seleccion)
            
            # Obtener el índice de la factura seleccionada
            idx_seleccionado = opciones_seleccion.index(seleccion)
            factura_principal = datos_facturas[idx_seleccionado]
            
            # Mostrar resultado de la suma
            st.success(f"**Resultado del control interno:**")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="Factura Conservada", value=factura_principal['ID Interno'])
                st.caption(f"UUID Completo: {factura_principal['UUID (Folio Fiscal)']}")
            with col2:
                # Aquí sumamos TODO el monto del XML y se lo asignamos a la factura elegida
                st.metric(label="Monto Consolidado (Suma Total)", value=f"${monto_total_xml:,.2f}")
                st.caption(f"Original: ${factura_principal['Monto Relacionado']:,.2f} + Ajustes detectados.")
                
            # Crear un botón para descargar un reporte limpio en Excel/CSV si lo necesitas
            reporte_final = pd.DataFrame([{
                'Factura_Control': factura_principal['ID Interno'],
                'UUID_Oficial': factura_principal['UUID (Folio Fiscal)'],
                'Monto_Consolidado': monto_total_xml
            }])
            
            csv = reporte_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar datos consolidados (CSV)",
                data=csv,
                file_name=f"pago_consolidado_{factura_principal['ID Interno']}.csv",
                mime='text/csv',
            )
            
    except Exception as e:
        st.error(f"Hubo un error al procesar el archivo XML. Asegúrate de que sea un CFDI de pago válido. Error: {e}")
