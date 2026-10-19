# Guía de Demostración: Merkle Audit System

Esta guía está diseñada como tu "guion" paso a paso para la defensa de tesis. Sigue este orden para mostrar la funcionalidad del sistema de manera lógica, dramática e impactante ante los jurados.

---

## 🎬 Fase 1: Inicialización (El Entorno)

**Objetivo:** Demostrar que el ecosistema entero se despliega de forma automatizada y está listo para producción.

1. Abre tu terminal.
2. Ejecuta el comando mágico: `bash start_all.sh`
3. **Puntos a mencionar al jurado:**
   * *"Con un solo script levantamos la Blockchain local (Ganache), desplegamos el Smart Contract automáticamente, encendemos el backend en Python (FastAPI) y lanzamos los dos frontends en React."*
   * Muestra brevemente cómo la terminal compila e imprime la dirección del contrato desplegado (`Contract deployed to: 0x...`).

---

## 🏦 Fase 2: Operación Normal (El Simulador)

**Objetivo:** Mostrar cómo se capturan los datos en el sistema bancario simulado.

1. Abre en tu navegador el **Simulador** en `http://localhost:5174`.
2. **Login:** Muestra la pantalla de inicio de sesión. Selecciona a **Ana Torres (cajero)** y entra.
3. **Generar Eventos:**
   * Haz clic en **Transacciones** y genera un par de *Depósitos* y *Retiros*.
   * Pasa a **Usuarios** y dale a *Crear Usuario*.
   * **Puntos a mencionar:** *"Cada evento que genero aquí representa una acción en el core bancario. Al momento de ejecutarse, el evento es enviado al servidor de auditoría."*
4. **Cierra sesión:** Usa el botón de *Salir* en la cabecera.

---

## 📊 Fase 3: Auditoría y Blockchain (El Dashboard)

**Objetivo:** Explicar el Árbol de Merkle y la inmutabilidad de Blockchain.

1. Abre el **Dashboard** en `http://localhost:5173`.
2. Muestra los indicadores principales (Total Logs, Batches, etc.).
3. Ve a la sección de **Batches (Lotes)** en el menú lateral.
4. **Cierre de Batch:**
   * Selecciona el Batch actual (estará en estado `open`) y dale al botón de "Detalle".
   * Haz clic en el botón naranja **"🔒 Cerrar Lote (Forzar)"**.
   * Explica: *"Para no saturar la red blockchain, agrupamos los logs en bloques (Batches). Al cerrarlo, la criptografía entra en acción."*
5. **Animación del Árbol de Merkle:**
   * Baja hasta el visor del árbol en ese batch cerrado.
   * Haz clic en el botón azul **"▶️ Recrear Cálculo del Árbol"**.
   * Explica: *"Aquí vemos cómo los hashes de cada log se emparejan matemáticamente (H(A) + H(B)). La pantalla nos va mostrando cómo sube el cálculo nivel por nivel hasta obtener una única huella digital: La Merkle Root."*
6. **Anclaje Blockchain:**
   * Sube al botón verde **"⛓️ Anclar en Blockchain"** y presiónalo.
   * Deja que el jurado vea el Stepper animado y la terminal simulada (`eth_sendTransaction`, `Minando Bloque...`).
   * Explica: *"En este momento, la aplicación se comunica con el Smart Contract en la red de Ethereum (Ganache). Estamos guardando la Raíz de Merkle de forma permanente e inmutable. A partir de este segundo, la historia no puede ser reescrita."*

---

## 🦹‍♂️ Fase 4: El Ataque (Demostración de Hackeo)

**Objetivo:** Simular que un atacante (ej. DBA interno corrupto) altera la base de datos de un log antiguo que ya fue asegurado por la blockchain.

1. Vuelve al **Simulador** (`http://localhost:5174`).
2. **Login de Atacante:** Inicia sesión con el perfil especial de **"Atacante Externo (hacker)"**.
3. **Ejecuta el Exploit:**
   * Busca en el timeline el evento que acabas de enviar (y que ya está anclado en el lote).
   * Haz clic en el botón rojo: **"Ejecutar Exploit (Alterar Payload)"**. (Cambiará a verde "BD Alterada").
   * Explica: *"Este botón simula un ataque directo a la base de datos SQL. Estamos inflando el monto multiplicándolo por 100 y evadiendo los controles de la aplicación (inyección SQL). En un sistema bancario tradicional, el auditor leería la base de datos y vería el fraude como si fuera un registro legítimo."*

---

## 🚨 Fase 5: Detección Forense (El Clímax)

**Objetivo:** Demostrar el poder de la auditoría Merkle frente a manipulaciones avanzadas.

1. Vuelve inmediatamente a la pestaña del **Dashboard** (`http://localhost:5173`).
2. **El Escáner SOC:**
   * Verás una alerta de pantalla negra con luces rojas parpadeantes tipo sirena: **BRECHA DE INTEGRIDAD DETECTADA**.
   * Lee la alerta al jurado mostrando las cajas de hashes. Explica: *"Nuestro escáner de integridad SOC ha calculado el hash de los datos actuales y se ha dado cuenta de que no coincide con el hash original. La alteración ha sido descubierta."*
3. **Verificación On-Chain:**
   * Haz clic en el botón de la alerta: *"Verificar Integridad en Blockchain"*.
   * Te llevará a la pantalla de validación criptográfica.
   * Pega el ID del log vulnerado (se copia desde la alerta) y dale a validar.
   * El sistema consultará el Smart Contract y arrojará el resultado: **RECHAZADO**.
   * Conclusión: *"La Blockchain confirma que ese registro es fraudulento, demostrando que nuestro sistema de Auditoría Merkle es 100% efectivo contra la alteración maliciosa de datos históricos."*

---

🎉 **Fin de la Demo.** Con esta secuencia, abarcarás el ciclo completo del software, la criptografía y la seguridad de forma impecable. ¡Mucho éxito en tu defensa!
