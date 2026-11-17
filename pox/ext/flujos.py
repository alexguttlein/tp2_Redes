# Import some POX stuff
from pox.core import core                       # Main POX object
import pox.openflow.libopenflow_01 as of        # OpenFlow 1.0 library
from pox.lib.addresses import EthAddr, IPAddr   # Address types
from pox.lib.packet.ethernet import ethernet
import logging
import pox.lib.packet as pkt
from pox.lib.packet.arp import arp
from pox.proto.arp_helper import send_arp_request



PUBLIC_MAC = EthAddr("00:00:00:aa:aa:aa")   # MAC del router hacia la red pública
PUBLIC_PORT = 1                             # Puerto del switch conectado a la red pública
PRIVATE_MAC = EthAddr("00:00:00:bb:bb:bb")  # MAC del router hacia la red privada

def flujos(self, transferencia):

    #SALIENTE

    fm_out = of.ofp_flow_mod()
    fm_out.idle_timeout = 50
    fm_out.match.in_port = transferencia["private_switch_port"]
    fm_out.match.dl_type = pkt.ethernet.IP_TYPE
    fm_out.match.nw_proto = transferencia["protocol"]
    fm_out.match.nw_src = transferencia["private_ip"]
    fm_out.match.nw_dst = transferencia["remote_ip"]
    fm_out.match.tp_src = transferencia["private_port"]
    fm_out.match.tp_dst = transferencia["remote_port"]

    fm_out.actions.append(of.ofp_action_nw_addr.set_src(transferencia["public_ip"]))
    fm_out.actions.append(of.ofp_action_tp_port.set_src(transferencia["nat_port"]))
    fm_out.actions.append(of.ofp_action_dl_addr.set_src(PUBLIC_MAC))
    fm_out.actions.append(of.ofp_action_dl_addr.set_dst(transferencia["remote_mac"]))
    fm_out.actions.append(of.ofp_action_output(port=PUBLIC_PORT))
    self.connection.send(fm_out)

    #ENTRANTE

    fm_in = of.ofp_flow_mod()
    fm_in.idle_timeout = 50
    fm_in.flags |= of.OFPFF_SEND_FLOW_REM
    fm_in.match.in_port = PUBLIC_PORT
    fm_in.match.dl_type = pkt.ethernet.IP_TYPE
    fm_in.match.nw_proto = transferencia["protocol"]
    fm_in.match.nw_src = transferencia["remote_ip"]
    fm_in.match.nw_dst = transferencia["public_ip"]
    fm_in.match.tp_src = transferencia["remote_port"]
    fm_in.match.tp_dst = transferencia["nat_port"]

    fm_in.actions.append(of.ofp_action_nw_addr.set_dst(transferencia["private_ip"]))
    fm_in.actions.append(of.ofp_action_tp_port.set_dst(transferencia["private_port"]))
    fm_in.actions.append(of.ofp_action_dl_addr.set_src(PRIVATE_MAC))
    fm_in.actions.append(of.ofp_action_dl_addr.set_dst(transferencia["private_mac"]))
    fm_in.actions.append(of.ofp_action_output(port=transferencia["private_switch_port"]))
    self.connection.send(fm_in)
