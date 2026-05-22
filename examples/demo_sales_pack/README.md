# Orvo Brain — Sales Demo Pack

Demo determinística para mostrarle a una PyME argentina/LatAm qué recibiría por WhatsApp sin pedir credenciales ni tocar sus sistemas.

## Cómo usarlo en una demo

1. Abrí este README o compartí los archivos `*.whatsapp.txt`.
2. Elegí el caso más parecido al prospecto: día normal, crisis de stock o multi-canal.
3. Copiar y pegar el bloque de WhatsApp y explicar: métricas, alerta y acción sugerida.
4. Cerrá con el valor: menos ventas perdidas, menos pauta desperdiciada y más control diario.

## Mensajes listos para copiar

### Reporte normal — día bueno

Ventas por encima del promedio, stock sano, bajo gasto en ads. Muestra un día típico sin alertas críticas.

Archivo sugerido: `pyme-normal.whatsapp.txt`

```text
🧠 Orvo Brain — Artemea — Flores
Reporte diario · 2026-05-20

📊 Métricas
- Ventas de hoy: ARS 285.000
- Promedio reciente: ARS 240.000
- Órdenes: 19
- Stock disponible: 180 units
- Conversaciones sin responder: 2
- Gasto en anuncios: ARS 18.500

📣 Publicidad
- Gasto del día: ARS 18.500
- ROAS estimado: 15.4x

🚨 Alertas
✅ Sin alertas críticas por ahora.

🔗 Fuentes: Demo Tiendanube
```

### Stock crítico + ads activos — alerta urgente

Ventas en caída, stock de solo 3 unidades, 12 conversaciones sin responder y $25.000 gastados en ads. Demuestra el valor de la detección temprana para evitar pérdidas.

Archivo sugerido: `pyme-stock-crisis.whatsapp.txt`

```text
🧠 Orvo Brain — Café de Barrio — Colegiales
Reporte diario · 2026-05-20

📊 Métricas
- Ventas de hoy: ARS 95.000
- Promedio reciente: ARS 180.000
- Stock disponible: 3 units
- Conversaciones sin responder: 12
- Gasto en anuncios: ARS 25.000

📣 Publicidad
- Gasto del día: ARS 25.000
- ROAS estimado: 3.8x

🚨 Alertas
🟡 Ventas 47% debajo del promedio: Las ventas de hoy están por debajo del promedio reciente.
   Acción: Revisá campañas activas, productos principales y mensajes pendientes antes de cerrar el día.
🟡 Conversaciones sin responder: Hay 12 conversaciones pendientes que pueden frenar ventas.
   Acción: Responder primero consultas de compra, envíos, talles/precios y reclamos recientes.
🔴 Ads activos con stock bajo — pausar campañas: Quedan 3 unidades en stock pero hay campañas activas con $25,000 ARS de gasto. Seguir invirtiendo en ads con stock insuficiente genera frustración y abandono de carrito.
   Acción urgente: Pausar todas las campañas que promocionen... (ver reporte completo)
```

### Multi-canal — Tiendanube + MercadoLibre + Meta Ads

Negocio con ventas en dos canales y gasto en publicidad. Muestra el balance de canales, ROAS estimado y detección de desbalance.

Archivo sugerido: `pyme-multi-canal.whatsapp.txt`

```text
🧠 Orvo Brain — ModaSud — Buenos Aires
Reporte diario · 2026-05-20

📊 Métricas
- Ventas Tiendanube hoy: ARS 320.000
- Ventas MercadoLibre hoy: ARS 510.000
- Pedidos Tiendanube hoy: 22
- Pedidos MercadoLibre hoy: 35
- Stock disponible: 95 units
- Conversaciones sin responder: 4
- Gasto en anuncios: ARS 42.000

📦 Canales
- Tiendanube: ARS 320.000
- MercadoLibre: ARS 510.000
- Total: ARS 830.000

📣 Publicidad
- Gasto del día: ARS 42.000
- ROAS estimado: 19.8x

🚨 Alertas
ℹ️ Revenue total multi-canal hoy: TN: $320,000 + ML: $510,000 = $830,000 ARS en total entre canales.
   Acción: Monitorear la proporción entre canales para detectar cambios de tendencia.
🟡 Canal Tiendanube posiblemente sub-rendimiento: MercadoLibre generó 59% más revenue que Tiendanube hoy. Revisá si la tienda Tiendanube está funcionando correctamente.
   Acción: Verificá que los productos, precios y el checkout de Tiendanube estén activos. Considerá aumentar tráfico directo a la tienda propia.

🔗 Fuentes: Demo Multi-canal
```

## Objeciones frecuentes

- **¿Inventan números?** No: cada métrica e insight sale con Fuentes verificables.
- **¿Necesito integrar todo para verlo?** No: este pack es sembrado y sirve para validar valor antes de conectar datos reales.
- **¿Qué se implementa primero?** Un reporte diario por WhatsApp con el conector que la PyME ya usa: CSV, Sheets, Tiendanube, MercadoLibre o Meta Ads.

## Promesa comercial

Orvo Brain no es otro tablero: resume cada mañana qué cambió, por qué importa y qué acción concreta tomar.
