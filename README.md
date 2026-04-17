# Motor de Cuadratura Farmacia: iBot vs Transbank

Este programa automatiza la conciliación de caja, comparando el reporte de ventas de iBot contra el reporte del portal Transbank.

## 🧠 ¿Cómo funciona el "Cerebro" del Programa?

El programa realiza los siguientes pasos lógicos para analizar tus archivos:

### 1. Lectura Inteligente de Archivos 📂
- **Excel con Formato Diferente**: El programa es capaz de detectar si tu Excel de iBot tiene los títulos en la primera línea o en la segunda (como en el caso de "Ventas - IBOT").
- **Columnas**: Busca automáticamente columnas clave como "Tipo de pago" y "Total", sin importar si están escritas con mayúsculas o minúsculas.

### 2. Filtrado y Limpieza 🧹
- **Solo Transbank**: Filtra automáticamente las ventas de iBot que dicen "Transbank" en el tipo de pago.
- **Normalización**: Limpia los montos (elimina signos $, puntos) y convierte las fechas y horas a un formato comparable.

### 3. El Algoritmo de Coincidencia (Matching) 🤝
Aquí ocurre la magia. El programa toma cada venta de iBot y busca su "pareja" en Transbank siguiendo estas reglas:
1.  **Mismo Monto**: El valor debe ser exacto.
2.  **Tolerancia de Tiempo**: Entiende que en la farmacia a veces se pasa la tarjeta y se digita la venta horas después.
    - Tiene una "memoria" de **4 HORAS**.
    - Ejemplo: Venta real (tarjeta) a las 17:22 y digitada en el PC a las 19:42 -> **¡Es un MATCH!** ✅

### 4. Reporte Simplificado 📊
El resultado final se muestra limpio y directo:
- **✅ Coincidencias Exactas**: Ventas que calzan perfecto (o con pocos minutos de diferencia). Estas se "aprueban" en silencio.
- **⚠️ Coincidencias con Desfase (>30 min)**: Aquí es donde verás casos como el del *Clopidogrel*. El programa te avisa: "Encontré este monto, pero con mucha diferencia de hora. Revísalo".
- **❌ Diferencias Reales (Desactivado temporalmente)**: Si activaras la vista completa, verías también lo que sobró o faltó sin explicación.

---
**Desarrollado para simplificar tu cierre de caja.**
