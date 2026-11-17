# TA-048 Redes - Trabajo Práctico 2: SDN / NAT

## Entorno de Trabajo y Ejecución

### Requisitos

- Python 3
- Mininet
- POX controller

### Instalación de POX

Clonar el repositorio oficial:
https://github.com/noxrepo/pox.git

### Ubicación del controlador

El archivo (`protorouter.py`) debe ubicarse en el directorio `pox/ext/`

### Ejecución del controlador

Desde una terminal, ejecutar:  
`python3 pox/pox.py log.level --DEBUG protorouter`

### Ejecución de la topología

En otra terminal, ejecutar:  
`sudo python3 topo.py`

### Orden de ejecución recomendado

- Iniciar el controlador POX.
- Ejecutar la topología en Mininet.
- Verificar que el switch se conecte al controlador.

### Verificación básica

- Iniciar la red.
- Desde la CLI de Mininet:
    - Probar conectividad: `h2 ping h1`


## Conceptos clave y archivos con los que estamos trabajando

### Conceptos y Palabras para leer antes de ponerse a hacer algo del TP

1. ¿Qué es una SDN (Software-Defined Networking)?

Es una arquitectura de red que separa el plano de control (la lógica que decide cómo se enruta el tráfico) del plano de datos (los switches físicos o virtuales que reenvían los paquetes). Esto permite programar y gestionar toda la red de forma lógicamente centralizada mediante software.

2. ¿Qué es POX?

Es un marco de trabajo (framework) desarrollado en Python que actúa como controlador SDN. Se encarga de ejecutar la lógica del plano de control y comunicarse con los switches de la red a través del protocolo OpenFlow.

3. ¿Qué es NAT y PAT?

NAT (Network Address Translation): Mecanismo de capa de red que reescribe las direcciones IP para permitir que una red con direcciones privadas se comunique con redes externas.

PAT (Port Address Translation o NAPT): Extensión de NAT que añade los puertos de la capa de transporte (TCP/UDP) a la tabla de traducción. Permite que cientos de dispositivos de una red privada compartan una única dirección IP pública de cara a Internet.

4. ¿Qué es OpenFlow?

Es el protocolo estándar de la interfaz "sur" (southbound interface) que conecta al controlador SDN con los switches. Define cómo el controlador puede consultar el estado de la red, recibir paquetes desconocidos y registrar reglas de coincidencia y acción (match + action) en las tablas de flujo de los switches.

5. ¿Qué es MAC?

Es la dirección de Control de Acceso al Medio (Media Access Control). Es un identificador físico de 48 bits (6 bytes) grabado de fábrica en cada tarjeta de interfaz de red (NIC). Tiene una estructura plana (no jerárquica) y se utiliza para identificar dispositivos dentro de una misma red local (LAN).

6. ¿Qué es el protocolo ARP?

El Protocolo de Resolución de Direcciones (Address Resolution Protocol) opera entre la capa de red y la de enlace. Su función principal es traducir una dirección IP de destino en su correspondiente dirección MAC física para poder entregar tramas dentro de la misma subred.

7. ¿Qué es traducir direcciones IP?

Es el proceso mediante el cual un dispositivo intermedio (como un router o un switch SDN) modifica los campos IP de Origen o IP de Destino en la cabecera del datagrama IPv4 mientras este atraviesa el equipo.

8. En palabras simples, ¿qué se pide cuando se debe implementar un NAT saliente con traducción por puertos PAT?

Se pide que cuando un host interno (192.168.1.X:puerto_privado) envíe un paquete a la red pública:

El controlador/router modifique el paquete saliente reemplazando su IP/puerto de origen por la IP pública del NAT y un puerto dinámico asignado.

Registre esa equivalencia en una tabla PAT.

Cuando llegue la respuesta desde la WAN a esa IP pública y puerto asignado, consulte la tabla, restaure la IP/puerto privado original del host y se lo reenvíe.

9. ¿Qué es resolver direcciones MAC mediante ARP dinámico?

Es el proceso mediante el cual el router o host no tiene grabadas las direcciones MAC de forma fija en el código ("hardcodeadas"), sino que:

Emite una consulta ARP Request por difusión (broadcast) a toda la subred: ¿Quién tiene la IP X.X.X.X?.

El destinatario responde con un mensaje ARP Reply unidifusión (unicast) enviando su dirección MAC.

El solicitante guarda esa correspondencia en su caché/tabla ARP para usarla en los siguientes envíos.

### Archivos en los que debemos implementar código

- **`topo.py`:** define la red emulada en Mininet: el switch, los hosts, sus direcciones IP/MAC, rutas por defecto y enlaces. Aquí se agregan los clientes privados y se prepara la topología para probar el controlador, sin depender de entradas ARP estáticas.

- **`pox/ext/protorouter.py`:** implementa el componente de POX que controla el switch OpenFlow. Procesa paquetes IPv4 y ARP, resuelve dinámicamente las MAC, mantiene paquetes pendientes mientras espera una respuesta ARP y administra las traducciones PAT de ida y vuelta. También aplica las modificaciones necesarias a los paquetes para reenviarlos entre la red privada y la pública. Según el enunciado, este controlador debe además instalar flujos para que el switch procese el tráfico de conexiones ya establecidas.

Los demás archivos de POX son parte del controlador provisto; en particular, `pox/ext/skeleton.py` es un ejemplo de componente y `pox/ext/nat.py` no contiene la implementación de este TP.
