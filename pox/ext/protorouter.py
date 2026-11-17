# Import some POX stuff
from pox.core import core                       # Main POX object
import pox.openflow.libopenflow_01 as of        # OpenFlow 1.0 library
from pox.lib.addresses import EthAddr, IPAddr   # Address types
from pox.lib.packet.ethernet import ethernet
import logging
from pox.lib.packet.arp import arp
from pox.proto.arp_helper import send_arp_request

from flujos import flujos

NAT_PORT_MIN = 20000
NAT_PORT_MAX = 40000

log = logging.getLogger("protorouter")
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def log_color(color, msg):
    log.info(f"{color}{msg}{RESET}")


PRIVATE_SUBNET = IPAddr("192.168.1.0")      # Red interna
PRIVATE_MASK = 24                           # Máscara de la red interna
PRIVATE_IP = IPAddr("192.168.1.254")        # IP del router en la red privada
PUBLIC_IP = IPAddr("200.0.0.254")           # IP del router en la red pública
PUBLIC_MAC = EthAddr("00:00:00:aa:aa:aa")   # MAC del router hacia la red pública
PRIVATE_MAC = EthAddr("00:00:00:bb:bb:bb")  # MAC del router hacia la red privada
PUBLIC_PORT = 1                             # Puerto del switch conectado a la red pública


class ProtoRouter(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)
        self.public_arp = {}
        self.pending_packets = {}
        self.arp_request_in_progress = set()

        self.pat_out = {} #PAT es un nat por puertos
        self.pat_in={}
        self.siguiente_puerto_publico = NAT_PORT_MIN
            

    def _handle_PacketIn(self, event):
        if not event.parsed.parsed:
            log.warning("[DROP] PacketIn con trama no reconocida. POX no pudo decodificar el paquete.")
            return

        packet = event.parsed


        if event.parsed.type == ethernet.IP_TYPE:
            self.handle_ip(event)
        elif packet.type == ethernet.ARP_TYPE:
            self.handle_arp(event,packet)
        else:
            log_color(YELLOW, f"Paquete ignorado: protocolo distinto de IPv4.")


    """
    Maneja las ip's que llegan al switch, y decide si son de la red privada o no. Si son de la red privada, se encarga de
    instalar los flujos de salida y entrada para que el paquete pueda salir hacia la red pública
    y que la respuesta pueda volver hacia la red privada. Si no son de la red privada, se ignoran. 

    """
    def handle_ip(self, event):
        packet = event.parsed
        ip_pkt = packet.payload
        in_port = event.port

        log_color(
            YELLOW, f"RECIBIDO: {ip_pkt.srcip} → {ip_pkt.dstip} | "
            f"MAC: {packet.src} → {packet.dst} | In Port: {in_port}")


        if ip_pkt.srcip.inNetwork(PRIVATE_SUBNET,PRIVATE_MASK):
            log_color(GREEN, f"MATCH SALIENTE: {ip_pkt.srcip}:{ip_pkt.payload.srcport}-> {ip_pkt.dstip}:{ip_pkt.payload.dstport}")

            dst_ip = ip_pkt.dstip

            if dst_ip not in self.public_arp:
                if dst_ip not in self.pending_packets:
                    self.pending_packets[dst_ip] = []
                self.pending_packets[dst_ip].append(event)

                if dst_ip not in self.arp_request_in_progress:
                    self.arp_request_in_progress.add(dst_ip)
                    send_arp_request(
                        connection=self.connection,
                        ip=dst_ip,
                        port=PUBLIC_PORT,
                        src_mac=PUBLIC_MAC,
                        src_ip=PUBLIC_IP
                    )
                return

            dst_mac = self.public_arp[dst_ip]

            key_out = (ip_pkt.srcip, ip_pkt.payload.srcport, ip_pkt.protocol)

            if key_out not in self.pat_out:
                pub_port = self.siguiente_puerto_publico
                self.siguiente_puerto_publico +=1

                if self.siguiente_puerto_publico > NAT_PORT_MAX: 
                    self.siguiente_puerto_publico = NAT_PORT_MIN

                self.pat_out[key_out] = pub_port
                self.pat_in[(pub_port, ip_pkt.protocol)] = (ip_pkt.srcip,ip_pkt.payload.srcport,in_port,packet.src)

                transferencia = {
                    "private_ip": ip_pkt.srcip,
                    "private_port": ip_pkt.payload.srcport,
                    "private_mac": packet.src,
                    "private_switch_port" :in_port,

                    "public_ip" : PUBLIC_IP,
                    "nat_port" : pub_port,
                    "remote_ip": ip_pkt.dstip,
                    "remote_port": ip_pkt.payload.dstport,
                    "remote_mac" : dst_mac,
                    "protocol": ip_pkt.protocol
                }

                flujos(self,transferencia)

                self.send_outgoing_packet(transferencia,event)

            else:
                pub_port = self.pat_out[key_out]

                transferencia = {
                    "private_ip": ip_pkt.srcip,
                    "private_port": ip_pkt.payload.srcport,
                    "private_mac": packet.src,
                    "private_switch_port" :in_port,

                    "public_ip" : PUBLIC_IP,
                    "nat_port" : pub_port,
                    "remote_ip": ip_pkt.dstip,
                    "remote_port": ip_pkt.payload.dstport,
                    "remote_mac" : dst_mac,
                    "protocol": ip_pkt.protocol
                }
        else:
            self.send_incoming_packet(event, packet, ip_pkt)

    """
    Este handle arp maneja el protocolo ARP (Protocolo de Resolución de Direcciones), en el controlador.
    
    Responde arp.REQUEST dirigidas a las ip's del nat (lan/wan), mandando la mac virtual que corresponde
    con un mensaje PacketOut.

    Procesa las arp.REPLY que llegan del puerto publico para guardar la direccion mac del servidor externo y mandar
    los paquetes ip que estaban en espera retenidos esperando esa dirección.
    """
    def handle_arp(self, event, paquete):
        paquete_arp = paquete.payload

        if event.port != PUBLIC_PORT and paquete_arp.protodst.inNetwork(
            PRIVATE_SUBNET,PRIVATE_MASK
        ):
            if paquete_arp.protodst != PRIVATE_IP: 
                return


        if paquete_arp.opcode == arp.REQUEST and paquete_arp.protodst in(
            PRIVATE_IP, PUBLIC_IP
        ):
            respuesta_mac = PRIVATE_MAC if paquete_arp.protodst == PRIVATE_IP else PUBLIC_MAC
            respuesta_ip = PRIVATE_IP if paquete_arp.protodst == PRIVATE_IP else PUBLIC_IP

            respuesta_arp = arp()
            respuesta_arp.opcode = arp.REPLY
            respuesta_arp.hwsrc = respuesta_mac
            respuesta_arp.protosrc = respuesta_ip
            respuesta_arp.hwdst = paquete_arp.hwsrc
            respuesta_arp.protodst = paquete_arp.protosrc

            respuesta_ethernet = ethernet(type=ethernet.ARP_TYPE, src = respuesta_mac, dst = paquete.src)
            respuesta_ethernet.payload = respuesta_arp #osea, la respuesta de ethernet contiene la respuesta arp

            mensaje = of.ofp_packet_out(data=respuesta_ethernet.pack())
            mensaje.actions.append(of.ofp_action_output(port=event.port))
            self.connection.send(mensaje) 
            log_color(GREEN,f"Respuesta ARP: Mac {respuesta_mac} para la ip {respuesta_ip}")

        elif(
            paquete_arp.opcode == arp.REPLY and event.port == PUBLIC_PORT and paquete_arp.protodst == PUBLIC_IP
        ):
            target_ip = paquete_arp.protosrc
            target_mac = paquete_arp.hwsrc

            self.public_arp[target_ip] = target_mac
            self.arp_request_in_progress.discard(target_ip)

            log_color(GREEN,f"Ahora el servidor público {target_ip} esta en MAC {target_mac}")
            self.process_pending_packets(target_ip, target_mac)

        
    """
    Se encarga de los paquetes pendientes de aquellas MAC's que todavia no se conocen dentro de nuestro programa
    Por eso se llama pending, porque quedan esperando a ser mandandos hasta que se resuelva la dirección MAC del servidor externo.
    """
    def process_pending_packets(self,ip,mac):
        if ip in self.pending_packets:
            log_color(GREEN, f"Procesando {len(self.pending_packets[ip])} paquetes pendientes para {ip}")
            for event in self.pending_packets[ip]:
                self.handle_ip(event)

            del self.pending_packets[ip]


    """
    Maneja el tráfico saliente desde la LAN hacia la WAN (traduccion PAT)
    Reescribe la IP y puerto de origen por la IP publica del router y el puerto NAT asignado, 
    y actualiza las direcciones mac para enviar el paquete a la WAN.
    """
    def send_outgoing_packet(self, trans, event):
        msg = of.ofp_packet_out(data=event.ofp, in_port=trans["private_switch_port"])
        msg.actions.append(of.ofp_action_nw_addr.set_src(trans["public_ip"]))
        msg.actions.append(of.ofp_action_tp_port.set_src(trans["nat_port"]))
        msg.actions.append(of.ofp_action_dl_addr.set_src(PUBLIC_MAC))
        msg.actions.append(of.ofp_action_dl_addr.set_dst(trans["remote_mac"]))
        msg.actions.append(of.ofp_action_output(port=PUBLIC_PORT))
        self.connection.send(msg)


    """
    Para el trafico de la WAN hacia la LAN (destraduccion del PAT)
    Restaura la ip y el puerto (privados) del destino original, viendo la tabla
    pat_in y reenvia el paquete hacia la MAC y puerto del switch donde esta el host privado
    """
    def send_incoming_packet(self,event,packet,ip_pkt):

        paquete_transporte = ip_pkt.payload
        key_in = (paquete_transporte.dstport,ip_pkt.protocol)

        if key_in not in self.pat_in:
            log_color(RED, f"Descartando entrante: No hay un PAT para el puerto publico {paquete_transporte.dstport}")
            return

        ip_privada, puerto_privado, target_port, target_mac = self.pat_in[key_in]

        log_color(CYAN, f"ENVIANDO PAT (WAN -> LAN): {ip_pkt.srcip}:{paquete_transporte.srcport} → {ip_privada}:{puerto_privado} | Out Port: {target_port}")

        msg = of.ofp_packet_out(data=event.ofp, in_port =PUBLIC_PORT)
        msg.actions.append(of.ofp_action_nw_addr.set_dst(ip_privada))
        msg.actions.append(of.ofp_action_tp_port.set_dst(puerto_privado))

        msg.actions.append(of.ofp_action_dl_addr.set_src(PRIVATE_MAC)) 
        msg.actions.append(of.ofp_action_dl_addr.set_dst(target_mac))

        msg.actions.append(of.ofp_action_output(port=target_port))

        self.connection.send(msg)


    def handle_flow_removal(self,event):
        if event.ofp.reason != of.OFPRR_IDLE_TIMEOUT: 
            return

        match = event.ofp.match

        if match.tp_dst is not None and match.nw_proto is not None:
            key_in = (match.tp_dst,match.nw_proto)

            if key_in in self.pat_in:
                priv_ip, priv_port, _, _ = self.pat_in[key_in]
                key_out = (priv_ip,priv_port, match.nw_proto)

                del self.pat_in[key_in]
                self.pat_out.pop(key_out,None)
        
                log_color(YELLOW, f"TIMEOUT: Conexión {priv_ip}:{priv_port} TIMEOUTE, {match.tp_dst} LIBERADO")




def launch():

    routers ={}

    def start_switch(event):
        log_color(YELLOW, f"Iniciando ProtoRouter para Switch {event.connection.dpid}")
        routers[event.connection.dpid] = ProtoRouter(event.connection)


    def handle_flow_removed(event):
        router = routers.get(event.connection.dpid)

        if router:
            router.handle_flow_removal(event)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
    core.openflow.addListenerByName("FlowRemoved",handle_flow_removed)


