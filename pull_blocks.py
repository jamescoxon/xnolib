#!/bin/env python3
import random
import socket
import argparse

from peercrawler import get_random_peer
from pynanocoin import *

def parse_args():
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-b', '--beta', action='store_true', default=False,
                       help='use beta network')
    group.add_argument('-t', '--test', action='store_true', default=False,
                       help='use test network')

    parser.add_argument('-p', '--peer',
                        help='peer to contact for frontiers (if not set, one is randomly from peer crawler)')
    parser.add_argument('-a', '--account', type=str, default=None,
                        help='The account you want to pull blocks from')
    return parser.parse_args()


def main():
    args = parse_args()

    ctx = livectx
    if args.beta: ctx = betactx
    if args.test: ctx = testctx

    account = ctx["genesis_pub"]
    if args.account is not None:
        if len(args.account) == 64:
            account = args.account
        else:
            account = acctools.account_key(args.account).hex()

    if args.peer:
        peeraddr, peerport = parse_endpoint(args.peer, default_port=ctx['peerport'])
    else:
        peer = get_random_peer(ctx, lambda p: p.score >= 1000)
        peeraddr, peerport = str(peer.ip), peer.port

    print('Connecting to [%s]:%s' % (peeraddr, peerport))
    with get_connected_socket_endpoint(peeraddr, peerport) as s:
        blocks = get_account_blocks(ctx, s, account)

        blockman = block_manager(ctx, None, None)
        blocks_pulled = len(blocks)
        while len(blocks) != 0:
            block = blocks.pop()
            print(block)
            blockman.process(block)

        print(blockman)
        print("blocks pulled: %d" % blocks_pulled)

if __name__ == "__main__":
    main()
