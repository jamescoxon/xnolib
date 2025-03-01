#!/bin/env python3
#
# Example usage on test network:
# ./confirm_req.py -t -H 687CEA7076C43E914942E36A234F8A92A1D518239653D3B954FACF87D927F300:21C49DE85134375C96C695BB367F7A4444F517EC730116EAA1AA884B1CF7054E

import sys
import time
import argparse
import datetime

import common
from pynanocoin import *
from msg_handshake import node_handshake_id
from peercrawler import *
import confirm_ack


class confirm_req:

    @classmethod
    def parse(cls, hdr, payload):
        if hdr.block_type() == block_type_enum.not_a_block:
            req = confirm_req_hash.parse(hdr, payload)
        else:
            req = confirm_req_block.parse(hdr, payload)
        return req


class confirm_req_hash(confirm_req):
    def __init__(self, hdr, hash_pairs):
        assert(isinstance(hdr, message_header))
        assert(len(hash_pairs) > 0)
        hdr.set_item_count(len(hash_pairs))
        hdr.set_block_type(block_type_enum.not_a_block)
        self.hdr = hdr
        self.hash_pairs = hash_pairs

    @classmethod
    def parse(self, hdr, data):
        assert  isinstance(hdr, message_header)
        assert(len(data) / 64 == hdr.count_get())

        hash_pairs = []
        for i in range(0, hdr.count_get()):
            hash_pairs.append(common.hash_pair.parse(data[0:64]))
            data = data[64:]

        return confirm_req_hash(hdr, hash_pairs)

    def serialise(self):
        data = self.hdr.serialise_header()
        for h in self.hash_pairs:
            data += h.serialise()
        return data

    def is_response(self, ack):
        assert(isinstance(ack, confirm_ack.confirm_ack_block) or isinstance(ack, confirm_ack.confirm_ack_hash))
        if isinstance(ack, confirm_ack.confirm_ack_hash):
            for h in self.hash_pairs:
                if h.hsh not in ack.hashes:
                    return False

        elif isinstance(ack, confirm_ack.confirm_ack_block):
            assert(len(self.hash_pairs) == 1)
            for h in self.hash_pairs:
                if h.hsh != ack.block.hash():
                    return False

        return True

    def __str__(self):
        string = str(self.hdr) + "\n"
        for i in range(1, len(self.hash_pairs) + 1):
            string += "Pair %d:\n" % i
            string += str(self.hash_pairs[i-1])
        return string


class confirm_req_block(confirm_req):
    def __init__(self, hdr, block):
        # TODO: Fill in the headers block_type and item count here
        # Block has to be an instance of a block class
        assert(isinstance(hdr, message_header))
        block_type = block.get_type_int()
        self.hdr = hdr
        self.hdr.set_block_type(block_type)
        self.hdr.set_item_count(1)
        self.block = block

    def serialise(self):
        assert(self.hdr.block_type() in range(2, 7))
        data = self.hdr.serialise_header()
        data += self.block.serialise(False)
        return data

    @classmethod
    def parse(cls, hdr, data):
        assert hdr.block_type() in range(2, 7)
        block = None
        if hdr.block_type() == 2:
            block = block_send.parse(data)
        elif hdr.block_type() == 3:
            block = block_receive.parse(data)
        elif hdr.block_type() == 4:
            block = block_open.parse(data)
        elif hdr.block_type() == 5:
            block = block_change.parse(data)
        elif hdr.block_type() == 6:
            block = block_state.parse(data)
        return confirm_ack.confirm_ack_block(hdr, block)

    def is_response(self, ack):
        assert(isinstance(ack, confirm_ack.confirm_ack_block) or isinstance(ack, confirm_ack.confirm_ack_hash))

        if isinstance(ack, confirm_ack.confirm_ack_block):
            if self.block.hash() != ack.block.hash():
                return False

        if isinstance(ack, confirm_ack.confirm_ack_hash):
            if self.block.hash() not in ack.hashes:
                return False

        return True

    def __str__(self):
        string = str(self.hdr) + "\n"
        string += str(self.block)
        return string


def get_next_confirm_ack(s):
    hdr, data = get_next_hdr_payload(s)
    while hdr.msg_type != message_type(5):
        hdr, data = get_next_hdr_payload(s)
    return hdr, data


def send_confirm_req_block(ctx, s):
    block = block_open(ctx["genesis_block"]["source"], ctx["genesis_block"]["representative"],
                       ctx["genesis_block"]["account"], ctx["genesis_block"]["signature"],
                       ctx["genesis_block"]["work"])

    print("The block we send hash: %s" % hexlify(block.hash()))

    outcome = confirm_block(ctx, block, s)

    if not outcome:
        print("block %s not confirmed!" % hexlify(block.hash()))
    else:
        print("block %s confirmed!" % hexlify(block.hash()))


def send_example_confirm_req_hash(ctx, s):
    block = block_open(ctx["genesis_block"]["source"], ctx["genesis_block"]["representative"],
                       ctx["genesis_block"]["account"], ctx["genesis_block"]["signature"],
                       ctx["genesis_block"]["work"])

    # print(block)

    outcome = confirm_blocks_by_hash(ctx, convert_blocks_to_hash_pairs([block]), s)

    if not outcome:
        print("blocks not confirmed!")
    else:
        print("blocks confirmed")


def search_for_response(s, req):
    assert(isinstance(req, confirm_req_block) or isinstance(req, confirm_req_hash))
    starttime = time.time()
    while time.time() - starttime <= 10:
        hdr, data = get_next_confirm_ack(s)
        ack = confirm_ack.confirm_ack.parse(hdr, data)
        assert ack

        if req.is_response(ack):
            return ack

    return None


def convert_blocks_to_hash_pairs(blocks):
    pairs = []
    for b in blocks:
        pair = common.hash_pair(b.hash(), b.root())
        pairs.append(pair)
    return pairs


def confirm_block(ctx, block, s):
    hdr = message_header(ctx["net_id"], [18, 18, 18], message_type(4), 0)
    req = confirm_req_block(hdr, block)
    s.send(req.serialise())

    resp = search_for_response(s, req)
    print(resp)

    if resp is None:
        return False
    else:
        return True


def get_confirm_block_resp(ctx, block, s):
    hdr = message_header(ctx["net_id"], [18, 18, 18], message_type(4), 0)
    req = confirm_req_block(hdr, block)
    s.send(req.serialise())

    resp = search_for_response(s, req)

    return resp


def confirm_blocks_by_hash(ctx, pairs, s):
    assert(isinstance(pairs, list))
    hdr = message_header(ctx["net_id"], [18, 18, 18], message_type(4), 0)
    req = confirm_req_hash(hdr, pairs)
    s.send(req.serialise())

    resp = search_for_response(s, req)
    print(resp)
    print('Response is valid:', resp.is_valid())

    return resp is not None


def confirm_req_peer(ctx, block, pair, peeraddr=None, peerport=None):
    assert (pair is None if block is not None else pair is not None)

    s = get_connected_socket_endpoint(peeraddr, peerport)
    with s:

        signing_key, verifying_key = node_handshake_id.keypair()
        node_handshake_id.perform_handshake_exchange(ctx, s, signing_key, verifying_key)
        print('handshake done')

        s.settimeout(10)
        if pair is None:
            print("Confirm Block")
            outcome = confirm_block(ctx, block, s)
            print("Finished with confirmed status: %s" % outcome)
        else:
            print("Confirm Hash")
            outcome = confirm_blocks_by_hash(ctx, [pair], s)
            print("Finished with confirmed status: %s" % outcome)


def main():
    # Example hash pair:
    #   hash: 991CF190094C00F0B68E2E5F75F6BEE95A2E0BD93CEAA4A6734DB9F19B728948
    #   root: E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA
    # Known voting peer: ::ffff:94.130.135.50
    args = parse_args()

    ctx = livectx
    if args.beta: ctx = betactx
    if args.test: ctx = testctx

    pair = None
    peeraddr = None
    peerport = None
    block = None

    if args.hash is not None:
        raw_pair = args.hash.split(':')
        if len(raw_pair) == 1:
            pair = common.hash_pair(binascii.unhexlify(raw_pair[0]), b'\x00' * 32)
        else:
            pair = common.hash_pair(binascii.unhexlify(raw_pair[0]), binascii.unhexlify(raw_pair[1]))
    else:
        block = block_open(ctx["genesis_block"]["source"], ctx["genesis_block"]["representative"],
                           ctx["genesis_block"]["account"], ctx["genesis_block"]["signature"],
                           ctx["genesis_block"]["work"])

    if args.peer is not None:
        peeraddr, peerport = parse_endpoint(args.peer, default_port=ctx['peerport'])

    else:
        peer = get_random_peer(ctx, lambda p: p.score >= 1000 and p.ip.is_ipv4() and p.is_voting)
        peeraddr = str(peer.ip)
        peerport = peer.port

    print('Connecting to [%s]:%s' % (peeraddr, peerport))
    confirm_req_peer(ctx, block, pair, peeraddr=peeraddr, peerport=peerport)


def parse_args():
    parser = argparse.ArgumentParser()

    group1 = parser.add_mutually_exclusive_group(required=True)
    group1.add_argument('-B', '--block', action="store_true", default=False)
    group1.add_argument('-H', '--hash', type=str, default=None,
                        help='hash or hash-root pair in the form "hash:root"')

    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument('-b', '--beta', action='store_true', default=False,
                        help='use beta network')
    group2.add_argument('-t', '--test', action='store_true', default=False,
                        help='use test network')

    parser.add_argument('-p', '--peer',
                        help='peer to contact for frontiers (if not set, one is randomly selected using DNS)')

    return parser.parse_args()


if __name__ == "__main__":
    main()
