# -*- coding: utf-8 -*-
"""
    cupyoftee.network
    ~~~~~~~~~~~~~~~~~

    Query the servers for information.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import time
import socket
from math import log
from datetime import datetime


GAMETYPES = dict(zip(range(3), ('dm', 'tdm', 'ctf')))


class ServerError(Exception):
    pass


class Syncable(object):
    last_sync = None

    def sync(self):
        try:
            self._sync()
        except (socket.error, socket.timeout, IOError):
            return False
        self.last_sync = datetime.utcnow()
        return True


class ServerBrowser(Syncable):

    def __init__(self, addr):
        self.addr = addr
        self.servers = {}
        while not self.sync():
            time.sleep(5)

    def _sync(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(5)
        s.sendto('\x20\x00\x00\x00\x00\x48\xff\xff\xff\xffreqt', self.addr)
        data = s.recvfrom(1024)[0][14:]
        s.close()

        to_delete = set(self.servers)
        for n in xrange(0, len(data) / 6):
            addr = ('.'.join(map(str, map(ord, data[n * 6:n * 6 + 4]))),
                    ord(data[n * 6 + 5]) * 256 + ord(data[n * 6 + 4]))
            server_id = '%s:%d' % addr
            if server_id in self.servers:
                if not self.servers[server_id].sync():
                    continue
            else:
                try:
                    self.servers[server_id] = Server(addr, self, server_id)
                except ServerError:
                    pass
            to_delete.discard(server_id)

        for server_id in to_delete:
            self.servers.pop(server_id, None)


class Server(Syncable):

    def __init__(self, addr, master, server_id):
        self.addr = addr
        self.id = server_id
        self.master = master
        if not self.sync():
            raise ServerError('server not responding in time')

    def _sync(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.sendto('\xff\xff\xff\xff\xff\xff\xff\xff\xff\xffgief', self.addr)
        bits = s.recvfrom(1024)[0][14:].split('\x00')
        s.close()
        self.version, server_name, self.map = bits[:3]
        self.name = server_name.decode('latin1')
        self.gametype_id, self.flags, self.progression, player_count, \
            self.max_players = map(int, bits[3:8])
        self.gametype = GAMETYPES.get(self.gametype_id, 'unknown')
        self.players = []
        for i in xrange(player_count):
            self.players.append(Player(self, bits[8 + i * 2].decode('latin1'),
                                       int(bits[8 + i * 2 + 1])))
        self.players.sort(key=lambda x: -x.score)
        self.player_count = len(self.players)


class Player(object):

    def __init__(self, server, name, score):
        self.server = server
        self.name = name
        self.score = score
        self.size = round(100 + log(max(score, 1)) * 25, 2)
