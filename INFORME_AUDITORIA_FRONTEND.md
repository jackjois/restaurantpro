# Informe de Auditoría Frontend — RestaurantPro

**Fecha:** 04/05/2026  
**Alcance:** 29 templates Jinja2, CSS inline, JavaScript embebido, flujo UX de POS restaurantero  
**Metodología:** Revisión estática completa de cada template, verificación de rutas de blueprints, validación de bloques heredados, análisis de XSS, lógica JS, accesibilidad y coherencia UX.

---

## 1. Resumen Ejecutivo

| Severidad | Cantidad |
|-----------|----------|
| CRITICAL  | 3        |
| HIGH      | 8        |
| MEDIUM    | 12       |
| LOW       | 9        |
| **Total** | **32**   |

Las 3 vulnerabilidades **CRITICAL** son fallas XSS que permiten inyección de scripts en datos controlados por el usuario (nombres de productos, notas de órdenes, nombres de mesas, etc.). Las de severidad **HIGH** incluyen routing roto en 404, falta de CSRF, riesgo de punto flotante en cálculos monetarios y ausencia de validación en montos de pago. Las **MEDIUM** y **LOW** cubren inconsistencias de UI, código duplicado, problemas de accesibilidad y fallas de UX específicas del contexto POS.

---

## 2. Estructura de Templates y Flujo UI

```
layout.html (base: sidebar, nav por rol, bloques: title, header_title, content, extra_css, extra_js)
├── dashboard.html
├── cashier/
│   ├── pos.html          (extiende layout)
│   ├── payments.html     (extiende layout)
│   ├── split_pay.html    (extiende layout)
│   └── ticket.html       (STANDALONE — no extiende layout)
├── orders/
│   ├── create.html       (extiende layout)
│   ├── list.html         (extiende layout)
│   ├── details.html      (extiende layout)
│   ├── kitchen.html      (extiende layout)
│   ├── comanda.html      (STANDALONE)
│   └── pos.html          (extiende layout)
├── floor/
│   └── floor.html        (STANDALONE — ~1200 líneas, SPA-like)
├── tables/
│   ├── list.html         (extiende layout)
│   └── monitor.html      (extiende layout)
├── products/
│   └── list.html         (extiende layout)
├── categories/
│   └── list.html         (extiende layout)
├── users/
│   └── list.html         (extiende layout)
├── settings/
│   └── index.html        (extiende layout)
├── reports/
│   ├── sales.html        (extiende layout)
│   ├── products.html     (extiende layout)
│   ├── shifts.html       (extiende layout)
│   └── shift_ticket.html (STANDALONE)
├── errors/
│   ├── 404.html          (extiende layout)
│   ├── 404_public.html   (STANDALONE)
│   └── 500.html          (STANDALONE)
├── login.html            (STANDALONE)
├── register.html         (STANDALONE)
└── carta-digital.html    (STANDALONE — usa Tailwind CSS)
```

---

## 3. Hallazgos Detallados

---

### CRITICAL-01 — Múltiples vulnerabilidades XSS por datos no escapados

**Severidad:** CRITICAL  
**Archivos afectados:**

| Archivo | Línea | Variable |
|---------|-------|----------|
| `cashier/payments.html` | 44 | `{{ item.product.name }}` |
| `cashier/split_pay.html` | ~item loop | `{{ item.product.name }}`, datos de items |
| `orders/details.html` | product loop | `{{ item.product.name }}`, `{{ item.notes }}` |
| `orders/kitchen.html` | items/notes | `{{ item.product.name }}`, `{{ item.notes }}` |
| `orders/comanda.html` | items/notes | `{{ item.product.name }}`, `{{ item.notes }}` |
| `orders/pos.html` | product catalog | `{{ product.name }}` |
| `orders/list.html` | order_number | `{{ order.order_number }}` |
| `products/list.html` | name/description | `{{ product.name }}`, `{{ product.description }}` |
| `tables/list.html` | table name | `{{ table.name }}` |
| `categories/list.html` | cat data | `{{ cat.name }}`, `{{ cat.description }}` |
| `users/list.html` | user data | `{{ user.username }}`, `{{ user.full_name }}` |
| `reports/sales.html` | order_number | `{{ order.order_number }}` |
| `carta-digital.html` | product data | nombres y descripciones de productos |
| `floor.html` | item/note data | nombres de productos, items, notas |
| `settings/index.html` | business data | `{{ config.business_name }}`, `{{ config.address }}`, `{{ config.phone }}` |
| `dashboard.html` | KPI values | valores numéricos renderizados |
| `register.html` | error display | mensajes de error |

**Descripción:** Jinja2 auto-escapa por defecto solo en archivos `.html`, pero si el entorno Jinja tiene `autoescape=False` o si se usa `|safe` en algún lugar, estos datos se convierten en vectores XSS directos. Además, en contexto de atributos HTML (ej. `title="{{ var }}"`), incluso con autoescape activo, ciertos payloads pueden escapar el atributo. Los nombres de productos, notas de órdenes, nombres de mesas y nombres de usuarios son todos datos controlables por operadores o, en el caso de carta-digital, potencialmente visibles para clientes.

**Impacto:** Ejecución arbitraria de JavaScript en el navegador de cualquier usuario que visualice estos datos. Robo de sesiones, redirecciones, modificación de la interfaz POS.

**Recomendación:** Verificar que `autoescape=True` esté activo en el Jinja Environment. Para datos en atributos HTML, usar `|e('attr')` o `|forceescape`. Agregar `Content-Security-Policy` headers como defensa en profundidad.

---

### CRITICAL-02 — Filtro personalizado `resolve_url` no registrado causará TemplateError en producción

**Severidad:** CRITICAL  
**Archivos afectados:**

| Archivo | Línea |
|---------|-------|
| `layout.html` | 12 |
| `login.html` | 9 |
| `register.html` | 9 |
| `settings/index.html` | 23 |
| `carta-digital.html` | 9 |

**Descripción:** El filtro `|resolve_url('')` se usa en múltiples templates críticos (layout — base de toda la app, login — entrada del sistema). Si este filtro no está registrado en `app.jinja_env.filters`, Jinja lanzará `TemplateAssertionError: no filter named 'resolve_url'` y la página completa fallará con error 500.

**Impacto:** Si el filtro no existe, **toda la aplicación es inaccesible** (layout.html afecta a todos los templates que lo extienden; login.html afecta el acceso al sistema).

**Recomendación:** Verificar en `app/__init__.py` o el archivo de configuración Jinja que exista:
```python
app.jinja_env.filters['resolve_url'] = resolve_url_function
```
Si el filtro no existe, implementarlo o eliminar su uso y reemplazar con `url_for` estático.

---

### CRITICAL-03 — Falta de token CSRF en formulario POST de creación de órdenes

**Severidad:** CRITICAL  
**Archivo:** `orders/create.html`  
**Línea:** Bloque `<form method="POST">`

**Descripción:** El formulario de creación de órdenes realiza un POST sin incluir un campo `csrf_token` hidden. Si la aplicación usa Flask-WTF o similar para protección CSRF, este formulario será rechazado. Si no usa protección CSRF, el formulario es vulnerable a ataques Cross-Site Request Forgery — un atacante puede crear órdenes fraudulentas en nombre de un usuario autenticado.

**Impacto:** Creación de órdenes falsas por CSRF, o error 400/403 si Flask-WTF rechaza el submit sin token.

**Recomendación:** Agregar `{{ csrf_token() }}` o `{{ form.csrf_token() }}` dentro del form. Verificar que todos los formularios POST de la aplicación incluyan el token.

---

### HIGH-01 — Routing roto en error 404: roles chef/cashier/waiter redirigen incorrectamente

**Severidad:** HIGH  
**Archivo:** `errors/404.html`  
**Línea:** 8

**Descripción:** La lógica de redirección en la página 404 solo maneja dos ramas:
```jinja
{% if current_user.role == 'admin' %}
    → url_for('dashboard.index')
{% else %}
    → url_for('tables.monitor')
```
Los roles `chef`, `cashier` y `waiter` caen todos en el `else` y son enviados a `tables.monitor`, que no es su página de destino correcta:
- **chef** → debería ir a `orders.kitchen`
- **cashier** → debería ir a `cashier.pos`
- **waiter** → debería ir a `orders.pos` o `floor.floor`

**Impacto:** Usuarios con roles operativos son redirigidos a una página que no corresponde a su función, rompiendo el flujo de trabajo tras encontrar un 404.

**Recomendación:** Implementar routing por rol completo:
```jinja
{% if current_user.role == 'admin' %} → dashboard.index
{% elif current_user.role == 'chef' %} → orders.kitchen
{% elif current_user.role == 'cashier' %} → cashier.pos
{% elif current_user.role == 'waiter' %} → orders.pos
{% else %} → tables.monitor {% endif %}
```

---

### HIGH-02 — Riesgo de punto flotante en cálculos monetarios del carrito JS

**Severidad:** HIGH  
**Archivos afectados:**

| Archivo | Línea aproximada |
|---------|------------------|
| `orders/pos.html` | bloques JS de cart/totals |
| `cashier/payments.html` | cálculos de cambio |
| `cashier/split_pay.html` | cálculos de saldo pendiente |
| `floor.html` | cálculos de subtotal/total |

**Descripción:** Los cálculos monetarios en JavaScript usan aritmética de punto flotante nativa (`0.1 + 0.2 !== 0.3`). En `orders/pos.html`, el carrito calcula totales con multiplicación y suma directa, usando `toFixed(2)` solo para display pero no para la lógica intermedia. Esto produce errores como:
```js
let total = 0;
items.forEach(i => { total += i.price * i.qty; });
// total puede ser 19.999999999999996 en vez de 20.00
```

**Impacto:** Totales incorrectos en el POS. Discrepancias de S/ 0.01 a S/ 0.05 en órdenes con múltiples items, especialmente con precios decimales (ej. S/ 15.90 × 3).

**Recomendación:** Usar cálculos en centavos (enteros) para toda la lógica, convirtiendo a decimales solo para display. Alternativamente, usar `Math.round(valor * 100) / 100` en cada paso intermedio.

---

### HIGH-03 — Sin validación de montos en pagos (negativos o excedentes)

**Severidad:** HIGH  
**Archivos afectados:**

| Archivo | Línea |
|---------|-------|
| `cashier/payments.html` | input de monto + numpad |
| `cashier/split_pay.html` | input de monto por método |

**Descripción:** Los formularios de pago no validan que el monto ingresado sea:
1. **Positivo** — un usuario puede ingresar montos negativos
2. **No exceda el total** — se puede pagar más del saldo pendiente sin advertencia
3. **Numérico** — la validación tipo `number` de HTML5 es insuficiente; el numpad personalizado permite construir valores inválidos

No hay validación client-side ni indicators de validación server-side en el template.

**Impacto:** Registros de pago con montos negativos (crédito fraudulento) o pagos excedentes que descuadran la caja.

**Recomendación:** Agregar validación JS que: (a) impida montos ≤ 0, (b) advierta si el monto excede el saldo, (c) bloquee el submit si el monto no es válido.

---

### HIGH-04 — Sin confirmación en acciones destructivas

**Severidad:** HIGH  
**Archivos afectados:**

| Archivo | Acción |
|---------|--------|
| `tables/list.html` | Eliminar mesa |
| `products/list.html` | Eliminar producto |
| `categories/list.html` | Eliminar categoría |
| `users/list.html` | Desactivar usuario, cambiar rol |

**Descripción:** Las acciones destructivas (eliminar mesa, producto, categoría; desactivar usuario; cambiar rol) no tienen diálogos de confirmación apropiados. En el mejor caso usan `confirm()` nativo del navegador, que es fácilmente evitable y visualmente inconsistente con el diseño premium de la app. En algunos casos no hay ninguna confirmación.

**Impacto:** Eliminación accidental de datos críticos del negocio (mesas, productos, categorías) con un solo click. En un entorno POS de alta velocidad, esto es especialmente probable.

**Recomendación:** Implementar modales de confirmación consistentes con el diseño de la app, con mensaje descriptivo del impacto y botón de confirmación rojo/danger.

---

### HIGH-05 — Framework CSS dual: Tailwind en carta-digital vs Bootstrap en todo lo demás

**Severidad:** HIGH  
**Archivo:** `carta-digital.html`  
**Línea:** bloque `<head>`

**Descripción:** `carta-digital.html` carga Tailwind CSS vía CDN mientras que **todos** los demás templates de la aplicación usan Bootstrap 5. Esto implica:
- Duplicación de ~200KB de CSS para una sola página
- Mantenimiento de dos sistemas de diseño
- Inconsistencia visual si un cliente ve la carta digital y luego otra parte de la app
- Riesgo de conflictos si en el futuro se integra la carta dentro del layout base

**Impacto:** Carga de página más lenta, duplicación de esfuerzo de diseño, potencial inconsistencia visual.

**Recomendación:** Migrar `carta-digital.html` a Bootstrap 5 para consistencia, o si se mantiene Tailwind, aislar completamente la página y documentar la decisión.

---

### HIGH-06 — `floor.html` es un monolito standalone de ~1200 líneas

**Severidad:** HIGH  
**Archivo:** `floor/floor.html`  
**Líneas:** todo el archivo (~1200)

**Descripción:** `floor.html` NO extiende `layout.html`. Carga Bootstrap y Bootstrap Icons independientemente, contiene toda su lógica de API fetch inline, manejo de estado de mesas, drag-and-drop, y UI de órdenes. Problemas:
- No hereda la barra lateral, nav, ni bloques de layout
- Duplica la carga de Bootstrap (ya lo carga layout.html)
- No comparte el estado de sesión/sidebar con el resto de la app
- Mantiene su propia lógica de autenticación/permisos
- CSS inline masivo que no se reutiliza

**Impacto:** Inconsistencia de navegación (sin sidebar), duplicación de dependencias, mantenimiento extremo, riesgo de desincronización con el layout base.

**Recomendación:** Refactorizar para extender `layout.html`, mover JS a archivos estáticos, extraer componentes CSS a `custom.css` compartido.

---

### HIGH-07 — Sin estados de carga en llamadas async

**Severidad:** HIGH  
**Archivos afectados:**

| Archivo | Operación |
|---------|-----------|
| `floor.html` | fetch de mesas, órdenes, cambios de estado |
| `orders/pos.html` | fetch de productos, envío de orden |
| `cashier/pos.html` | fetch de sesión de caja |
| `cashier/payments.html` | procesamiento de pago |

**Descripción:** Las llamadas `fetch()` en estos templates no muestran ningún indicador de carga (spinner, skeleton, barra de progreso) al usuario. Durante operaciones de red lentas (común en restaurantes con WiFi inestable), el usuario no tiene feedback de que la operación está en curso.

**Impacto:** Usuarios hacen click múltiple (double-submit), creando órdenes/pagos duplicados. O creen que la app "se colgó" y recargan la página, perdiendo datos.

**Recomendación:** Agregar spinners o skeleton loaders en cada operación async, deshabilitar botones durante la operación, y usar debounce/throttle en submits.

---

### HIGH-08 — CSS `.table-premium` y `.btn-action-dots` duplicados en 7 archivos

**Severidad:** HIGH  
**Archivos afectados:**

| Archivo | ~Líneas duplicadas |
|---------|--------------------|
| `orders/list.html` | 8-62 |
| `tables/list.html` | bloque `<style>` |
| `products/list.html` | bloque `<style>` |
| `users/list.html` | bloque `<style>` |
| `reports/sales.html` | bloque `<style>` |
| `reports/products.html` | bloque `<style>` |
| `reports/shifts.html` | 7-62 |

**Descripción:** ~60 líneas de CSS idénticas (`.table-premium`, `.btn-action-dots`) están copiadas textualmente en 7 templates. Cualquier cambio de diseño debe aplicarse 7 veces.

**Impacto:** Mantenimiento costoso, riesgo de inconsistencia visual si se actualiza solo en algunos archivos, aumento de peso de cada página.

**Recomendación:** Mover estos estilos a un archivo `static/css/custom.css` compartido y eliminar los bloques `<style>` inline.

---

### MEDIUM-01 — Formato de moneda inconsistente en toda la aplicación

**Severidad:** MEDIUM  
**Archivos afectados:** Múltiples

**Descripción:** No existe un enfoque consistente para formatear montos monetarios:

| Patrón | Archivos |
|--------|----------|
| `{{ item.subtotal }}` (sin formato) | `orders/details.html`, `orders/comanda.html` |
| `{{ "%.2f"\|format(valor) }}` | `reports/shifts.html`, `cashier/payments.html` |
| `toFixed(2)` en JS | `floor.html`, `orders/pos.html` |
| `S/ {{ valor }}` manual | varios |

Esto produce salidas como `S/ 15.5` en vez de `S/ 15.50`, o `S/ 1500` en vez de `S/ 1,500.00`.

**Recomendación:** Crear un filtro Jinja `|soles` que formatee consistentemente como `S/ 1,500.00` con separador de miles y 2 decimales. Usar `Intl.NumberFormat('es-PE', {style:'currency', currency:'PEN'})` en JS.

---

### MEDIUM-02 — `kitchen.html` usa `!important` para dark mode, rompiendo layout

**Severidad:** MEDIUM  
**Archivo:** `orders/kitchen.html`  
**Líneas:** bloque `<style>`

**Descripción:** KDS (Kitchen Display System) aplica dark mode con reglas como:
```css
body { background: #1a1a2e !important; }
.sidebar { background: #16213e !important; }
.nav { ... !important; }
```
Los `!important` sobreescriben forzosamente los estilos de `layout.html`, creando fragilidad: cualquier cambio en layout puede romper el dark mode, y el dark mode no se puede personalizar sin más `!important`.

**Impacto:** Mantenimiento frágil, riesgo de regresión visual con cambios en layout.

**Recomendación:** Usar una clase `.dark-mode` en `<body>` y selectores anidados sin `!important`. Alternativamente, que kitchen.html no extienda layout.html si necesita un diseño completamente diferente.

---

### MEDIUM-03 — Páginas standalone sin CSS/JS compartido

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Dependencias independientes |
|---------|-----------------------------|
| `floor.html` | Bootstrap, Bootstrap Icons, inline CSS/JS |
| `ticket.html` | CSS inline, Courier New |
| `comanda.html` | CSS inline, monospace |
| `shift_ticket.html` | CSS inline, Courier Prime |
| `carta-digital.html` | Tailwind CSS, Plus Jakarta Sans |
| `404_public.html` | CSS inline |
| `500.html` | CSS inline |

**Descripción:** Estas páginas cargan sus propias dependencias CSS/JS sin compartir un archivo `custom.css` o `common.js`. Si se cambia el logo, colores del brand, o tipografía, cada archivo standalone debe actualizarse individualmente.

**Recomendación:** Crear `static/css/print.css` compartido para tickets, y `static/css/standalone.css` para páginas públicas, con variables CSS compartidas.

---

### MEDIUM-04 — Font Inter referenciada pero no cargada en login/register

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Línea |
|---------|-------|
| `login.html` | CSS `font-family: 'Inter'` |
| `register.html` | CSS `font-family: 'Inter'` |

**Descripción:** Los templates de login y register usan `font-family: 'Inter', sans-serif` en sus estilos inline pero no incluyen el `<link>` de Google Fonts para cargar la tipografía Inter. El navegador usará `sans-serif` como fallback (generalmente Arial), creando una discrepancia visual con `dashboard.html` que sí carga Inter.

**Recomendación:** Agregar `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">` en el `<head>` de ambos archivos, o migrar a una fuente del sistema para eliminar la dependencia CDN.

---

### MEDIUM-05 — Auto-refresh en kitchen.html sin indicador visual ni control de usuario

**Severidad:** MEDIUM  
**Archivo:** `orders/kitchen.html`  
**Líneas:** bloque JS `setInterval` / `setTimeout`

**Descripción:** El KDS usa auto-refresh periódico pero: (a) no muestra al usuario cuándo fue la última actualización, (b) no permite pausar el refresh, (c) si el refresh falla (error de red), no hay indicación visual del error.

**Impacto:** Cocineros no saben si están viendo datos actualizados o stale. En caso de fallo de red, pueden estar cocinando órdenes ya canceladas.

**Recomendación:** Agregar un indicador "Última actualización: HH:MM:SS" visible, un botón de pausa de refresh, y un banner de error de conexión con retry manual.

---

### MEDIUM-06 — Sin manejo de errores en fetch() — errores silenciosos

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Operación |
|---------|-----------|
| `floor.html` | todas las llamadas fetch |
| `orders/pos.html` | envío de orden |
| `cashier/pos.html` | apertura/cierre de sesión |
| `cashier/payments.html` | procesamiento de pago |

**Descripción:** Las llamadas `fetch()` no manejan adecuadamente errores de red, respuestas 4xx/5xx, ni excepciones. Patrón típico:
```js
fetch(url, options).then(res => res.json())
  .then(data => { /* éxito */ });
// Sin .catch() — error silencioso
```

**Impacto:** Errores de red o del servidor no se muestran al usuario. La interfaz queda en estado inconsistente (ej. una orden que se creó en el servidor pero la UI no lo refleja porque el response falló).

**Recomendación:** Agregar `.catch()` con notificación visual al usuario (toast/alert), y verificar `res.ok` antes de parsear JSON.

---

### MEDIUM-07 — Monitor de mesas sin actualización en tiempo real

**Severidad:** MEDIUM  
**Archivo:** `tables/monitor.html`  
**Líneas:** bloque JS

**Descripción:** El monitor de mesas muestra estados con animaciones de pulso, pero no implementa WebSocket ni polling para actualización automática. El usuario debe recargar manualmente para ver cambios.

**Impacto:** En un entorno de alta rotación, el monitor muestra datos obsoletos. Mesas marcadas como "libre" pueden estar realmente ocupadas.

**Recomendación:** Implementar WebSocket (Socket.IO) o polling con `setInterval` para actualizar estados en tiempo real.

---

### MEDIUM-08 — Paginación inconsistente entre reportes

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Usa paginación |
|---------|----------------|
| `reports/sales.html` | Sí (Flask-Paginate) |
| `reports/products.html` | No |
| `reports/shifts.html` | Sí (Flask-Paginate) |

**Descripción:** Solo `sales.html` y `shifts.html` usan `shifts.iter_pages()` / paginación. `products.html` muestra todos los resultados sin paginación. Si un restaurante tiene cientos de productos, la página será extremadamente larga.

**Recomendación:** Agregar paginación consistente a `products.html`.

---

### MEDIUM-09 — Falta de validación client-side en formularios CRUD

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Formulario |
|---------|------------|
| `tables/list.html` | Crear/editar mesa (nombre, capacidad) |
| `products/list.html` | Crear/editar producto (precio, nombre) |
| `categories/list.html` | Crear/editar categoría |
| `users/list.html` | Editar usuario |
| `settings/index.html` | Configuración del negocio |

**Descripción:** Los formularios modales de CRUD no tienen validación client-side robusta. Problemas específicos:
- Precio de producto: acepta valores negativos o cero
- Capacidad de mesa: acepta 0 o negativos
- Nombre de mesa/producto: sin longitud mínima/máxima
- IGV (settings): sin rango válido (debe ser 0-100%)

**Recomendación:** Agregar `min`, `max`, `minlength`, `maxlength`, `pattern` en los inputs HTML5 y validación JS custom para reglas de negocio.

---

### MEDIUM-10 — Upload de imagen sin preview ni validación de tipo

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Campo |
|---------|-------|
| `products/list.html` | Imagen de producto |
| `settings/index.html` | Logo del negocio |

**Descripción:** Los campos de upload de imagen no muestran preview de la imagen seleccionada antes del submit, ni validan el tipo de archivo client-side. El usuario no sabe qué imagen está subiendo hasta después del submit.

**Recomendación:** Agregar preview con `FileReader` API y validar `accept="image/*"` con verificación de `file.type` en JS.

---

### MEDIUM-11 — KPIs del dashboard sin formateo numérico

**Severidad:** MEDIUM  
**Archivo:** `dashboard.html`  
**Líneas:** bloques de KPI cards

**Descripción:** Los valores de KPIs (ventas del día, número de órdenes, etc.) se muestran sin formato numérico localizado. Ejemplo: `1500` en vez de `1,500` o `S/ 1,500.00`. En un restaurante con ventas altas, los números grandes son difíciles de leer sin separadores.

**Recomendación:** Usar el filtro `|intcomma` (si se agrega) o `Intl.NumberFormat('es-PE')` para formatear KPIs.

---

### MEDIUM-12 — Numpad de pagos no tiene labels ARIA

**Severidad:** MEDIUM  
**Archivos afectados:**

| Archivo | Componente |
|---------|------------|
| `cashier/payments.html` | Numpad de monto |
| `cashier/split_pay.html` | Numpad de monto |

**Descripción:** Los botones del numpad (0-9, ., ←) no tienen `aria-label` ni `role="button"`. Un lector de pantalla no puede identificar la función de cada botón.

**Recomendación:** Agregar `aria-label` a cada botón del numpad (ej. `aria-label="Siete"`, `aria-label="Borrar"`).

---

### LOW-01 — Sin skip-nav link en layout.html

**Severidad:** LOW  
**Archivo:** `layout.html`  
**Línea:** inicio de `<body>`

**Descripción:** No existe un link "Saltar al contenido" para usuarios de teclado/lectores de pantalla. Navegar por la sidebar requiere múltiples tabs antes de llegar al contenido principal.

**Recomendación:** Agregar `<a href="#main-content" class="sr-only sr-only-focusable">Saltar al contenido</a>` al inicio del body.

---

### LOW-02 — KDS kitchen.html sin ARIA live regions

**Severidad:** LOW  
**Archivo:** `orders/kitchen.html`  
**Líneas:** contenedor de órdenes

**Descripción:** Las nuevas órdenes que aparecen en el KDS no se anuncian a lectores de pantalla. No hay `aria-live="polite"` o `aria-live="assertive"` en el contenedor de órdenes.

**Recomendación:** Agregar `aria-live="polite"` al contenedor de la lista de órdenes para que nuevas órdenes sean anunciadas.

---

### LOW-03 — Foco no se gestiona al abrir/cerrar modales

**Severidad:** LOW  
**Archivos afectados:** Todos los templates con modales Bootstrap

**Descripción:** Al abrir un modal (ej. crear mesa, editar producto), el foco no se mueve explícitamente al modal. Al cerrar, el foco no vuelve al botón que lo abrió. Usuarios de teclado pierden la referencia de foco.

**Recomendación:** Usar los eventos `shown.bs.modal` y `hidden.bs.modal` de Bootstrap para gestionar el foco programáticamente.

---

### LOW-04 — `orders/pos.html` — carrito no persiste ante recarga

**Severidad:** LOW  
**Archivo:** `orders/pos.html`  
**Líneas:** JS del carrito

**Descripción:** El estado del carrito se mantiene solo en variables JS en memoria. Si el usuario recarga la página accidentalmente (común en pantallas táctiles de POS), todos los items del carrito se pierden.

**Impacto:** Pérdida de trabajo del mesero/cajero, reingreso manual de items.

**Recomendación:** Persistir el carrito en `sessionStorage` o `localStorage` y restaurarlo al cargar la página.

---

### LOW-05 — Color de texto de badge en shifts.html puede fallar contraste WCAG

**Severidad:** LOW  
**Archivo:** `reports/shifts.html`  
**Línea:** 139-146

**Descripción:** Los badges de descuadre usan `bg-opacity-10` con `text-primary` o `text-danger`, que sobre fondo blanco pueden no cumplir WCAG AA (ratio de contraste mínimo 4.5:1 para texto normal).

**Recomendación:** Verificar contraste con herramientas como WebAIM Contrast Checker y ajustar colores si es necesario.

---

### LOW-06 — `comanda.html` y `ticket.html` no tienen `@media print` explícito

**Severidad:** LOW  
**Archivos afectados:**

| Archivo | 
|---------|
| `orders/comanda.html` |
| `cashier/ticket.html` |
| `reports/shift_ticket.html` |

**Descripción:** Los templates de impresión dependen del comportamiento por defecto del navegador para `window.print()`. No tienen reglas `@media print` explícitas para ocultar elementos no imprimibles o ajustar márgenes.

**Recomendación:** Agregar `@media print { ... }` con ajustes de margen, ocultación de scrollbars, y tamaño de papel.

---

### LOW-07 — Auto-actualización de `tables/monitor.html` puede consumir batería

**Severidad:** LOW  
**Archivo:** `tables/monitor.html`  
**Líneas:** JS de polling

**Descripción:** Si se implementa polling para el monitor, las animaciones de pulso CSS y el polling constante pueden consumir batería significativa en tablets usadas como display de cocina.

**Recomendación:** Usar `requestAnimationFrame` para animaciones, y `visibilitychange` API para pausar polling cuando la pestaña no está visible.

---

### LOW-08 — Botón "Ver/Imprimir" ticket usa `window.open` — puede ser bloqueado por popup blocker

**Severidad:** LOW  
**Archivo:** `reports/shifts.html`  
**Línea:** 154

**Descripción:** El botón de ticket usa `window.open(...)` para abrir una ventana popup. Los navegadores modernos bloquean popups por defecto si no son resultado directo de un click del usuario (y con delays, son bloqueados).

**Recomendación:** Usar `target="_blank"` en un `<a>` tag, o abrir en la misma pestaña con opción de volver.

---

### LOW-09 — `register.html` no indica requisitos de contraseña

**Severidad:** LOW  
**Archivo:** `register.html`  
**Líneas:** campo de password

**Descripción:** El campo de contraseña en el registro no muestra los requisitos mínimos (longitud, caracteres especiales, etc.) hasta que el usuario recibe un error.

**Recomendación:** Agregar texto de ayuda o un indicador de requisitos debajo del campo de contraseña.

---

## 4. Resumen por Categoría

| Categoría | Cantidad | Severidades |
|-----------|----------|-------------|
| Seguridad (XSS, CSRF) | 3 | CRITICAL |
| Errores de routing/lógica | 2 | CRITICAL, HIGH |
| Cálculos monetarios | 2 | HIGH, MEDIUM |
| Validación de formularios | 3 | HIGH, MEDIUM |
| UX / Flujo de trabajo | 4 | HIGH, MEDIUM |
| CSS / Diseño | 3 | HIGH, MEDIUM |
| Accesibilidad | 4 | MEDIUM, LOW |
| Mantenibilidad (duplicación) | 2 | HIGH, MEDIUM |
| Manejo de errores | 2 | MEDIUM |
| Performance / Carga | 2 | LOW |
| Print / Impresión | 2 | LOW |

---

## 5. Priorización de Corrección Recomendada

### Fase 1 — Crítico (1-3 días)
1. **CRITICAL-01**: Verificar autoescape y agregar CSP headers
2. **CRITICAL-02**: Verificar/registar filtro `resolve_url`
3. **CRITICAL-03**: Agregar CSRF token a orders/create.html

### Fase 2 — Alto (1-2 semanas)
4. **HIGH-01**: Corregir routing 404 por rol
5. **HIGH-02**: Migrar cálculos monetarios JS a centavos
6. **HIGH-03**: Validación de montos de pago
7. **HIGH-04**: Modales de confirmación para acciones destructivas
8. **HIGH-05**: Unificar carta-digital a Bootstrap o aislar documentadamente
9. **HIGH-06**: Refactorizar floor.html para extender layout
10. **HIGH-07**: Agregar estados de carga a operaciones async
11. **HIGH-08**: Extraer CSS duplicado a custom.css

### Fase 3 — Medio (2-4 semanas)
12. **MEDIUM-01** a **MEDIUM-12**: Formato de moneda, dark mode, validación, accesibilidad, manejo de errores, paginación, etc.

### Fase 4 — Bajo (continuo)
13. **LOW-01** a **LOW-09**: Accesibilidad avanzada, print CSS, persistencia de carrito, etc.

---

*Fin del informe.*
