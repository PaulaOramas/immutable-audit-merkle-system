# Análisis de Perfiles de Atacantes y Patrones de Vulnerabilidad

Para demostrar la robustez del sistema y tener un análisis forense completo, se han identificado **3 perfiles de atacantes** distintos que vulneraron o intentaron vulnerar el sistema de diferentes maneras. A continuación, se detalla el análisis táctico de cada uno, los patrones identificados y las tablas comparativas.

---

## 🦹‍♂️ Perfil 1: El Atacante Interno (DBA Corrupto / Insider Threat)

* **Tipo de Atacante:** Empleado con altos privilegios (Administrador de Base de Datos).
* **IP de Origen:** `192.168.1.105` (IP interna, red corporativa o VPN de empleado).
* **Vulnerabilidad Explotada:** Abuso de privilegios y acceso directo a la infraestructura.
* **Ataque Real (Cómo vulneró):** El atacante no usó la aplicación web. Aprovechando sus credenciales de DBA, accedió directamente al motor de la base de datos de producción mediante una consola SQL (`psql` o `pgAdmin`). Ejecutó comandos `UPDATE` a bajo nivel para alterar el monto de una transacción histórica, multiplicando el valor por 100 y modificando directamente el campo JSON del `payload` para beneficiar a una cuenta aliada. 
* **Patrones Identificados:**
  * Modificación de registros sin que exista un log de aplicación que lo respalde.
  * Acceso en horarios inusuales para el personal de TI (ej. 3:00 AM un domingo).
  * Cambios quirúrgicos: modificó exactamente un registro histórico sin tocar otros.
* **Cantidad de Accesos:** Entró **1 sola vez** a la base de datos (sesión de 12 minutos para ejecutar el script SQL y salir).
* **Respuesta de Merkle Audit:** Detectado por el **Escáner SOC**. Al modificar los datos sin recalcular la huella criptográfica, el hash guardado difiere del calculado, lanzando una **Brecha de Integridad**.

---

## 🕵️‍♂️ Perfil 2: El Cibercriminal Externo (Inyección SQL - APT)

* **Tipo de Atacante:** Hacker externo o grupo organizado.
* **IP de Origen:** `185.17.43.22` (IP geolocalizada en un servidor proxy/Tor en Europa del Este).
* **Vulnerabilidad Explotada:** Inyección SQL (SQLi) ciega en un endpoint de una API heredada (Legacy).
* **Ataque Real (Cómo vulneró):** Explotó una falta de sanitización de inputs en un módulo antiguo de reportes que aún estaba conectado a la base de datos principal. A través de inyecciones SQL automatizadas, logró "escapar" de la consulta original y forzar la inserción y modificación de transacciones en la tabla de logs para encubrir la sustracción de fondos hacia cuentas extranjeras.
* **Patrones Identificados:**
  * Tráfico anómalo: múltiples peticiones malformadas con comillas simples (`'`) y comandos SQL (`UNION SELECT`) en los parámetros de la URL.
  * *User-Agent* strings pertenecientes a herramientas de escaneo automatizado (ej. SQLmap).
  * Intentos repetitivos y secuenciales de acceso y manipulación.
* **Cantidad de Accesos:** Entró **45 veces** realizando intentos fallidos (reconocimiento) antes de lograr **1 acceso exitoso** que comprometió la integridad de la tabla.
* **Respuesta de Merkle Audit:** Altera registros que ya habían sido anclados a la blockchain. Al realizar la validación On-Chain, el Smart Contract rechaza la Merkle Root, detectando y exponiendo la alteración maliciosa de los historiales.

---

## 🎭 Perfil 3: Cuenta Comprometida (Phishing a Cajero - Robo de Identidad)

* **Tipo de Atacante:** Estafador mediante Ingeniería Social.
* **IP de Origen:** `203.0.113.89` (IP dinámica de un proveedor de internet móvil, ajena a la sucursal del banco).
* **Vulnerabilidad Explotada:** Falta de Autenticación Multifactor (MFA) y caída en campaña de Phishing.
* **Ataque Real (Cómo vulneró):** El atacante envió un correo fraudulento (clonado del área de TI del banco) a la cajera "Ana Torres". Al hacer clic, ella introdujo sus credenciales en una página falsa. El atacante usó estas credenciales legítimas para iniciar sesión en la plataforma frontal (`auditoriaMerkleFront`). Una vez dentro, ejecutó múltiples retiros fraccionados (Smurfing) hacia cuentas puente, aprobándolos él mismo con el nivel de acceso del cajero.
* **Patrones Identificados:**
  * Inicio de sesión exitoso al primer intento, pero desde un dispositivo, navegador y ubicación geográfica desconocidos.
  * Múltiples retiros rápidos por montos justo por debajo del límite de alerta automática (ej. 4 retiros de $9,900 en menos de 5 minutos).
  * Alta velocidad transaccional humana (imposible para una persona teclear tan rápido).
* **Cantidad de Accesos:** Entró **6 veces** en ráfagas cortas de 3 minutos a lo largo de un día para no mantener sesiones prolongadas abiertas.
* **Respuesta de Merkle Audit:** En este caso, el atacante usó las vías "legales" del sistema. Merkle Audit registró todos y cada uno de estos retiros en la Blockchain de forma inmutable. Aunque los datos no fueron alterados a nivel de base de datos, el auditor tiene un registro permanente, incuestionable e imborrable de la IP, la hora exacta y el usuario que realizó el fraude, facilitando el rastreo legal.

---

## 📊 Tablas Comparativas de Datos

### Resumen de Vectores de Ataque
| ID Atacante | Perfil | Origen (IP) | Método de Ingreso | Vulnerabilidad | Frecuencia de Acceso | Detección Merkle Audit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ATK-001** | DBA Corrupto | `192.168.1.105` (Interna) | Base de Datos (SQL Directo) | Abuso de Privilegios | 1 acceso (sesión larga) | Fallo en Hash Local (Alerta SOC) |
| **ATK-002** | Hacker Externo | `185.17.43.22` (Proxy) | Legacy API | Inyección SQL (SQLi) | 45 intentos + 1 éxito | Rechazo en Contrato Inteligente |
| **ATK-003** | Estafador (Phishing) | `203.0.113.89` (Móvil) | Interfaz Web (Frontend) | Robo de Credenciales | 6 accesos (ráfagas cortas) | Rastreo Inmutable (Trazabilidad) |

### Análisis de Comportamiento y Daño
| ID Atacante | Tipo de Daño | Modificó BD Histórica | Patrón Identificable | Velocidad del Ataque |
| :--- | :--- | :--- | :--- | :--- |
| **ATK-001** | Manipulación Financiera | **Sí** | Acceso a horas no laborables | Lento y Quirúrgico |
| **ATK-002** | Manipulación / Robo | **Sí** | Peticiones masivas de error | Rápido / Automatizado |
| **ATK-003** | Fraude Transaccional | No (creó nuevos logs) | Retiros fraccionados (Smurfing) | Rápido / Ráfagas |
