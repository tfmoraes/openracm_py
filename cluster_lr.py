import argparse
import bisect
import bsddb
import colorsys
import io
import math
import mmap
import os
import random
import signal
import struct
import sys
import threading
import time
import types

from bisect import bisect

import numpy as np

from cluster_loader import cluster_loader
import cy_corner_table
import laced_ring
import ply_reader
import ply_writer

STRUCT_FORMATS = {'v': 'clddd',
                  'L': 'clll',
                  'R': 'clll',
                  'S': 'clllll',

                  'V': 'cll',
                  'O': 'cll',
                  'C': 'cll',
                 }

RUNNING = 0

STRUCT_SIZES = {key:struct.calcsize(f) for (key, f) in STRUCT_FORMATS.items()}

class Ring:
    def __init__(self, l):
        self._data = l

    def __repr__(self):
        return repr(self._data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, i):
        return self._data[i]

    def append(self, item):
        self._data.append(item)

    def insert(self, index, item):
        self._data.insert(index, item)

    def index(self, item):
        return self._data.index(item)

    def pop(self, item=None):
        if item is None:
            return self._data.pop()
        return self._data.pop(item)

    def turn(self):
        last = self._data.pop(-1)
        self._data.insert(0, last)

    def rotate(self):
        first = self._data.pop(0)
        self._data.append(first)

    def first(self):
        return self._data[0]

    def last(self):
        return self._data[-1]

def calculate_d(cllr, vi):
    t = 0
    n = 0.0
    nvi = np.array(cllr.vertices[vi])
    for vj in cllr.get_ring0(vi):
        nvj = np.array(cllr.vertices[vj])
        t = t + (nvj - nvi)
        n += 1.0

    return t / n
    

def  taubin_smooth(cllr, l, m, steps):
    for s in xrange(steps):
        D = {}
        for i in xrange(cllr.m):
            D[i] = calculate_d(cllr, i)

        for i in xrange(cllr.m):
            p = np.array(cllr.vertices[i])
            pl = p + l*D[i]
            nx, ny, nz = pl
            cllr.vertices[i] = nx, ny, nz


def random_access(cllr, n):
    """
    Access randomly vertices from a mesh and access if ring-0
    cllr - A clustered laced ring structure
    n - The number of random access.
    """

    for i in xrange(n):
        vi = random.randint(0 , cllr.m - 1)
        v = cllr.vertices[vi]
        #for vj in cllr.get_ring0(vi):
            #pass

def access_vertex_from_files(cllr, f):
    fv = open(f)
    for vi in fv:
        v = cllr.vertices[int(vi)]

def lru(cl_usage):
    k = min(cl_usage, key=lambda x: cl_usage[x]['timestamp'])
    return k


def lu(cl_usage):
    k = min(cl_usage, key=lambda x: cl_usage[x]['access'])
    return k


def mru(cl_usage):
    k = max(cl_usage, key=lambda x: cl_usage[x]['timestamp'])
    return k


def mu(cl_usage):
    k = max(cl_usage, key=lambda x: cl_usage[x]['access'])
    return k


def randomized(cl_usage):
    k = random.choice(cl_usage.keys())
    return k


def lrfu(cl_usage):
    k = min(cl_usage, key=lambda x: cl_usage[x]['crf'])
    return k


class ClusterManager(object):
    def __init__(self, filename, qsize=10, scd_policy=lru, lbd=0.7, upd_cl_us=None):
        self.filename = filename
        self.scd_policy = scd_policy
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_isolated_vertices_file = os.path.splitext(filename)[0] + '_iv.hdr'
        index_corner_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_corner_vertice_file = os.path.splitext(filename)[0] + '_cv.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_cl.hdr'
        self.index_vertices = bsddb.btopen(index_vertices_file)
        self.index_isolated_vertices = bsddb.btopen(index_isolated_vertices_file)
        self.index_corners = bsddb.btopen(index_corner_file)
        self.index_corner_vertice = bsddb.btopen(index_corner_vertice_file)
        self.index_clusters = bsddb.btopen(index_clusters_file)

        self.iv_keys = sorted([int(i) + 1 for i in self.index_vertices.keys()])
        self.ic_keys = sorted([int(i) + 1 for i in self.index_corners.keys()])
        #self.icv_keys = sorted([int(i) + 1 for i in self.index_corner_vertice.keys()])

        self.cfile = io.open(filename, 'rb')
        #self.cfile = mmap.mmap(cfile.fileno(), 0, access=mmap.ACCESS_READ)
        self.load_header()

        self.cl_usage = {}
        self.queue_size = int(math.ceil((qsize / 100.0 * len(self.index_clusters))))
        self.timestamp = 0
        self.lbd = lbd

        self.wastings = []
        self.last_removed = -1
        self.last_loaded = -1

        self._n_load_clusters = {}
        self._n_unload_clusters = {}
        self.misses = 0
        self.hits = 0
        self.access = 0

        self.colour = 0

        self.to_clean = None

        self.__vertices = {}
        self.__L = {}
        self.__R = {}
        self.__O = {}
        self.__V = {}
        self.__C = {}
        self.__VOs = {}

        self.vertices = _DictGeomElemVertex(self, 'vertices', self.__vertices)
        self.L = _DictGeomElemVertex(self, 'L', self.__L)
        self.R = _DictGeomElemVertex(self, 'R', self.__R)
        self.O = _DictGeomElemCorners(self, 'O', self.__O)
        self.V = _DictGeomElemCorners(self, 'V', self.__V)
        self.C = _DictGeomElemVertexCluster(self, 'C', self.__C)
        self.VOs = _DictGeomElemVertex(self, 'VOs', self.__VOs)

        if upd_cl_us is None:
            self.update_cluster_usage = self._update_cluster_usage
        else:
            self.update_cluster_usage = types.MethodType(upd_cl_us, self)

        signal.signal(signal.SIGINT , lambda x, y: self.print_cluster_info())

        self.wait = threading.Lock()
        #threading.Thread(target=self._cleanup).start()

    def load_header(self):
        self.mr = int(self.cfile.readline().split(':')[1].strip())
        self.m = int(self.cfile.readline().split(':')[1].strip())
        self.number_triangles = int(self.cfile.readline().split(':')[1].strip())

    def _cleanup(self):
        while RUNNING:
            if self.to_clean is not None:
                self.wait.acquire()
                k = self.to_clean
                del self.cl_usage[k]
                del self.__vertices[k]
                del self.__L[k]
                del self.__R[k]
                del self.__VOs[k]
                del self.__O[k]
                del self.__V[k]
                del self.__C[k]

                self.last_removed = k

                if k == self.last_loaded:
                    self.wastings.append(k)

                try:
                    self._n_unload_clusters[k] += 1
                except KeyError:
                    self._n_unload_clusters[k] = 1

                self.to_clean = None
                self.wait.release()
            time.sleep(0.001)

    #@profile
    def load_cluster(self, cl):

        #self.wait.acquire()
        if len(self.cl_usage) >= self.queue_size:
            #print "The queue is full"
            k = str(self.scd_policy(self.cl_usage))
            self.to_clean = k
        #self.wait.release()
            del self.cl_usage[k]
            del self.__vertices[k]
            del self.__L[k]
            del self.__R[k]
            del self.__VOs[k]
            del self.__O[k]
            del self.__V[k]
            del self.__C[k]

            self.last_removed = k

            if k == self.last_loaded:
                self.wastings.append(k)

            try:
                self._n_unload_clusters[k] += 1
            except KeyError:
                self._n_unload_clusters[k] = 1

        init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
        self.cfile.seek(init_cluster)
        str_cluster = self.cfile.read(cluster_size)

        #vertices = {}

        #L = {}
        #R = {}
        #VOs = {}

        #V = {}
        #C = {}
        #O = {}
        #cluster = str_cluster
        #init = 0
        #cluster_size = len(cluster)
        #while init != cluster_size:
            #tmp = cluster[init: init + STRUCT_SIZES[cluster[init]]]
            #init += STRUCT_SIZES[cluster[init]]
            #t_element = tmp[0]
            ##cluster = cluster[STRUCT_SIZES[cluster[0]]::]

            #if t_element == 'v':
                #c_, v_id, vx, vy, vz = struct.unpack(STRUCT_FORMATS['v'], tmp) 
                #vertices[v_id] = [vx, vy, vz]

            #elif t_element == 'L':
                #c_, l0, l1, l2 = struct.unpack(STRUCT_FORMATS['L'], tmp) 
                #L[v_id] = [l0, l1, l2]

            #elif t_element == 'R':
                #c_, r0, r1, r2 = struct.unpack(STRUCT_FORMATS['R'], tmp) 
                #R[v_id] = [r0, r1, r2]

            #elif t_element == 'S':
                #c_, s0, s1, s2, s3, s4 = struct.unpack(STRUCT_FORMATS['S'], tmp)
                #VOs[v_id] = [s0, s1, s2, s3, s4]

            #elif t_element == 'V':
                #c_, c_id, v_id = struct.unpack(STRUCT_FORMATS['V'], tmp)
                #V[c_id] = v_id

            #elif t_element == 'C':
                #c_, v_id, c_id = struct.unpack(STRUCT_FORMATS['C'], tmp)
                #C[v_id] = c_id

            #elif t_element == 'O':
                #c_, c_id, c_o = struct.unpack(STRUCT_FORMATS['O'], tmp)
                #O[c_id] = c_o
                

        ##for l in cluster:
            ##if l:
                ##if l[0] == 'v':
                    ##tmp = l.split()
                    ##v_id = int(tmp[1])
                    ##vertices[v_id] = [float(i) for i in tmp[2:]]
                ##elif l[0] == 'L':
                    ##tmp = l.split()
                    ##L[v_id] = [int(tmp[1]), int(tmp[2]), int(tmp[3])]
                ##elif l[0] == 'R':
                    ##tmp = l.split()
                    ##R[v_id] = [int(tmp[1]), int(tmp[2]), int(tmp[3])]
                ##elif l[0] == 'S':
                    ##tmp = l.split()
                    ##v_id = int(tmp[1])
                    ##VOs[v_id] = [int(e) for e in tmp[2::]]

                ##elif l[0] == 'V':
                    ##tmp = l.split()
                    ##c_id = int(tmp[1])
                    ##v_id = int(tmp[2])
                    ##V[c_id] = v_id
                ##elif l[0] == 'C':
                    ##tmp = l.split()
                    ##v_id = int(tmp[1])
                    ##c_id = int(tmp[2])
                    ##C[v_id] = c_id
                ##elif l[0] == 'O':
                    ##tmp = l.split()
                    ##c_id = int(tmp[1])
                    ##c_o = int(tmp[2])
                    ##O[c_id] = c_o
        
        ##try:
            ##minv = min(vertices)
            ##maxv = max(vertices)
        ##except ValueError:
            ##minv = min(V)
            ##maxv = max(V)

        ##if minv == maxv:
            ##minv = min(V)
            ##maxv = max(V)

        vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

        self.__vertices[cl] = vertices
        self.__L[cl] = L
        self.__R[cl] = R
        self.__VOs[cl] = VOs
        self.__V[cl] = V
        self.__C[cl] = C
        self.__O[cl] = O

        try:
            self._n_load_clusters[cl] += 1
        except KeyError:
            self._n_load_clusters[cl] = 1
            self._n_unload_clusters[cl] = 0

        self.last_loaded = cl
        if self.last_removed == cl:
            self.wastings.append(cl)

        self.misses += 1

    def load_vertex_cluster(self, v_id):
        #print ">>>", v_id
        cl = self.index_vertices[str(v_id)]
        #print "Loading Cluster", cl
        return self.load_cluster(cl)

    def load_corner_cluster(self, c_id):
        #print ">>>", c_id
        cl = self.index_corners[str(c_id)]
        #print "Loading Cluster", cl
        return self.load_cluster(cl)

    def load_corner_vertice_cluster(self, v_id):
        #print ">>>", c_id
        cl = self.index_corner_vertice[str(v_id)]
        #print "Loading Cluster", cl
        return self.load_cluster(cl)

    def print_cluster_info(self):
        print "============================================================"
        for k in sorted(self._n_load_clusters, key=lambda x: int(x)):
            print k, self._n_load_clusters[k], self._n_unload_clusters[k]

        print "============================================================"
        print self.cl_usage
        print "============================================================"
        print sorted(self.wastings)
        sys.exit()

    def _update_cluster_usage(self, cl_key):
        self.timestamp += 1
        try:
            self.cl_usage[cl_key]['timestamp'] = self.timestamp
            self.cl_usage[cl_key]['access'] += 1
        except KeyError:
            self.cl_usage[cl_key] = {'timestamp': self.timestamp,
                                     'access': 1,}

    def print_hm_info(self):
        print self.queue_size, len(self.index_clusters), self.access, self.hits, self.misses, float(self.hits) / self.access


class _DictGeomElem(object):
    def __init__(self, clmrg, name, elems):
        self._elems = elems
        self._name = name
        self._clmrg = clmrg

    def __getitem__(self, key):
        self._clmrg.access += 1
        key = int(key)
        if self._name in ('V', 'O'):
            #idx = bisect(self._clmrg.ic_keys, key)
            cl = self._clmrg.index_corners[str(key)]
            try:
                e = self._elems[cl][key]
                self._clmrg.hits += 1
            except KeyError:
                self._clmrg.load_cluster(cl)
                e = self._elems[cl][key]
        elif self._name == 'C':
            #idx = bisect(self._clmrg.icv_keys, key)
            #cl = self._clmrg.index_corner_vertice[str(self._clmrg.icv_keys[idx] - 1)]
            cl = self._clmrg.index_corner_vertice[str(key)]
            try:
                e = self._elems[cl][key]
                self._clmrg.hits += 1
            except KeyError:
                self._clmrg.load_cluster(cl)
                e = self._elems[cl][key]
        else:
            if key >= self._clmrg.mr:
                cl = self._clmrg.index_isolated_vertices[str(key)]
            else:
                idx = bisect(self._clmrg.iv_keys, key)
                cl = self._clmrg.index_vertices[str(self._clmrg.iv_keys[idx] - 1)]
            try:
                e = self._elems[cl][key]
                self._clmrg.hits += 1
            except KeyError:
                self._clmrg.load_cluster(cl)
                self._clmrg.colour = [i*255 for i in colorsys.hls_to_rgb(random.randint(0, 360), random.random(), random.random())]
                try:
                    e = self._elems[cl][key]
                except KeyError, err:
                    print cl, key, self._name, self._clmrg.mr, idx
                    print self._clmrg.iv_keys
                    print self._clmrg.index_vertices
                    print self._elems
                    sys.exit()

        self._clmrg.update_cluster_usage(cl)
        return e

    def __setitem__(self, key, value):
        self._clmrg.access += 1
        try:
            if key >= self._clmrg.mr:
                cl = self._clmrg.index_isolated_vertices[str(key)]
            else:
                idx = bisect(self._clmrg.iv_keys, key)
                cl = self._clmrg.index_vertices[str(self._clmrg.iv_keys[idx] - 1)]
            self._elems[cl][key] = value
            self._clmrg.hits += 1
        except KeyError:
            self._clmrg.load_cluster(cl)
            self._elems[cl][key] = value

        self._clmrg.update_cluster_usage(cl)

    def __len__(self):
        return len(self._elems)


class _DictGeomElemCorners(_DictGeomElem):
    def __getitem__(self, key):
        self._clmrg.access += 1
        key = int(key)
        cl = self._clmrg.index_corners[str(key)]
        try:
            e = self._elems[cl][key]
            self._clmrg.hits += 1
        except KeyError:
            self._clmrg.load_cluster(cl)
            e = self._elems[cl][key]

        self._clmrg.update_cluster_usage(cl)
        return e


class _DictGeomElemVertexCluster(_DictGeomElem):
    def __getitem__(self, key):
        self._clmrg.access += 1
        key = int(key)
        #idx = bisect(self._clmrg.icv_keys, key)
        #cl = self._clmrg.index_corner_vertice[str(self._clmrg.icv_keys[idx] - 1)]
        cl = self._clmrg.index_corner_vertice[str(key)]
        try:
            e = self._elems[cl][key]
            self._clmrg.hits += 1
        except KeyError:
            self._clmrg.load_cluster(cl)
            e = self._elems[cl][key]
        self._clmrg.update_cluster_usage(cl)
        return e


class _DictGeomElemVertex(_DictGeomElem):
    #@profile
    def __getitem__(self, key):
        _clmrg = self._clmrg
        _clmrg.access += 1
        #key = int(key)
        s_key = str(key)

        if key >= _clmrg.mr:
            cl = _clmrg.index_isolated_vertices[s_key]
        else:
            idx = bisect(_clmrg.iv_keys, key)
            cl = _clmrg.index_vertices[str(_clmrg.iv_keys[idx] - 1)]
        try:
            e = self._elems[cl][key]
            _clmrg.hits += 1
        except KeyError:
            _clmrg.load_cluster(cl)
            _clmrg.colour = [i*255 for i in colorsys.hls_to_rgb(random.randint(0, 360), random.random(), random.random())]
            try:
                e = self._elems[cl][key]
            except KeyError, err:
                print cl, key, self._name, _clmrg.mr, idx
                print _clmrg.iv_keys
                print _clmrg.index_vertices
                print self._elems
                print ">>>>>"
                sys.exit()

        _clmrg.update_cluster_usage(cl)
        return e


class ClusteredLacedRing(laced_ring.LacedRing):
    def __init__(self, clmrg):
        self.cluster_manager = clmrg
        self.vertices = clmrg.vertices
        #self.faces = faces
        #self.edge_ring = edge_ring
        #self.m_t = m_t
        self.L = clmrg.L
        self.R = clmrg.R
        self.O = clmrg.O
        self.V = clmrg.V
        self.C = clmrg.C
        self.VOs = clmrg.VOs

        self.mr = self.cluster_manager.mr
        self.m = self.cluster_manager.m
        self.number_triangles = self.cluster_manager.number_triangles

    def get_vertex_coord(self, v_id):
        return self.vertices[v_id]


def create_clusters(lr, cluster_size):
    clusters = []
    n = -1
    v_id = 0
    print lr.mr, cluster_size
    inc_iv = {}
    inc_c = {}
    for t in xrange(0, lr.mr):
        if t % cluster_size == 0:
            n += 1
            clusters.append([])

        clusters[n].append(('v', v_id, lr.vertices[v_id][0], lr.vertices[v_id][1], lr.vertices[v_id][2]))
        clusters[n].append(('L', lr.L[v_id][0], lr.L[v_id][1], lr.L[v_id][2]))
        clusters[n].append(('R', lr.R[v_id][0], lr.R[v_id][1], lr.R[v_id][2]))

        vl = lr.L[v_id][0]
        vr = lr.L[v_id][0]

        if lr.L[v_id][2] or lr.R[v_id][2]:
            clusters[n].append(('S', v_id, lr.VOs[v_id][0], lr.VOs[v_id][1], lr.VOs[v_id][2], lr.VOs[v_id][3])) 

            for c0 in lr.VOs[v_id]:
                if c0 != -1:
                    c1 = lr.next_corner(c0)
                    c2 = lr.previous_corner(c0)

                    if not inc_c.get(c0, 0):
                        inc_c[c0] = 1
                        vc0 = lr.vertex(c0)
                        clusters[n].append(('V', c0, vc0))
                        clusters[n].append(('O', c0, lr.oposite(c0)[0]))
                        clusters[n].append(('C', vc0, c0))

                        if vc0 >= lr.mr and not inc_iv.get(vc0, 0):
                            inc_iv[vc0] = 1
                            clusters[n].append(('v', vc0, lr.vertices[vc0][0],
                                                lr.vertices[vc0][1],
                                                lr.vertices[vc0][2]))

                    if not inc_c.get(c1, 0):
                        inc_c[c1] = 1
                        vc1 = lr.vertex(c1)
                        clusters[n].append(('V', c1, vc1))
                        clusters[n].append(('O', c1, lr.oposite(c1)[0]))
                        clusters[n].append(('C', vc1, c1))
                        
                        if vc1 >= lr.mr and not inc_iv.get(vc1, 0):
                            inc_iv[vc1] = 1
                            clusters[n].append(('v', vc1, lr.vertices[vc1][0],
                                                lr.vertices[vc1][1],
                                                lr.vertices[vc1][2]))
                        
                    if not inc_c.get(c2, 0):
                        inc_c[c2] = 1
                        vc2 = lr.vertex(c2)
                        clusters[n].append(('V', c2, vc2))
                        clusters[n].append(('O', c2, lr.oposite(c2)[0]))
                        clusters[n].append(('C', vc2, c2))

                        if vc2 >= lr.mr and not inc_iv.get(vc2, 0):
                            inc_iv[vc2] = 1
                            clusters[n].append(('v', vc2, lr.vertices[vc2][0],
                                                lr.vertices[vc2][1],
                                                lr.vertices[vc2][2]))

        if vl >= lr.mr and not inc_iv.get(vl, 0):
            inc_iv[vl] = 1
            clusters[n].append(('v', vl, lr.vertices[vl][0], lr.vertices[vl][1], lr.vertices[vl][2]))
        
        if vr >= lr.mr and not inc_iv.get(vr, 0):
            inc_iv[vr] = 1
            clusters[n].append(('v', vr, lr.vertices[vr][0], lr.vertices[vr][1], lr.vertices[vr][2]))

        v_id += 1

    n += 1
    clusters.append([])
    #for v_id in xrange(lr.mr, lr.m):
        #if not inc_iv.get(v_id, 0):
            #if len(clusters[n]) == 1000:
                #clusters.append([])
                #n += 1
            #clusters[n].append(('v', v_id, lr.vertices[v_id][0], lr.vertices[v_id][1], lr.vertices[v_id][2]))

    print lr.mr, lr.m, lr.number_triangles, len(lr.vertices)
    i = 0
    for t in xrange(lr.mr * 2, lr.number_triangles):

        if i == 300:
            clusters.append([])
            n += 1
            i = 0

        c0 = lr.corner_triangle(t)
        c1 = lr.next_corner(c0)
        c2 = lr.previous_corner(c0)

        v0 = lr.vertex(c0)
        v1 = lr.vertex(c1)
        v2 = lr.vertex(c2)

        if v0 >= lr.mr and not inc_iv.get(v0, 0):
            inc_iv[v0] = 1
            clusters[n].append(('v', v0, lr.vertices[v0][0], lr.vertices[v0][1], lr.vertices[v0][2]))
        if v1 >= lr.mr and not inc_iv.get(v1, 0):
            inc_iv[v1] = 1
            clusters[n].append(('v', v1, lr.vertices[v1][0], lr.vertices[v1][1], lr.vertices[v1][2]))
        if v2 >= lr.mr and not inc_iv.get(v2, 0):
            inc_iv[v2] = 1
            clusters[n].append(('v', v2, lr.vertices[v2][0], lr.vertices[v2][1], lr.vertices[v2][2]))


        if not inc_c.get(c0, 0):
            clusters[n].append(('V', c0, lr.vertex(c0)))
            clusters[n].append(('C', v0, c0))
            clusters[n].append(('O', c0, lr.oposite(c0)[0]))

        if not inc_c.get(c1, 0):
            clusters[n].append(('V', c1, lr.vertex(c1)))
            clusters[n].append(('C', v1, c1))
            clusters[n].append(('O', c1, lr.oposite(c1)[0]))

        if not inc_c.get(c2, 0):
            clusters[n].append(('V', c2, lr.vertex(c2)))
            clusters[n].append(('C', v2, c2))
            clusters[n].append(('O', c2, lr.oposite(c2)[0]))

        i += 1

    return clusters

def save_clusters(lr, clusters, filename):
    with file(filename, 'w') as cfile:
        # indexes
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_isolated_vertices_file = os.path.splitext(filename)[0] + '_iv.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_cl.hdr'
        index_corner_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_corner_vertice_file = os.path.splitext(filename)[0] + '_cv.hdr'
        index_vertices = bsddb.btopen(index_vertices_file)
        index_isolated_vertices = bsddb.btopen(index_isolated_vertices_file)
        index_corners = bsddb.btopen(index_corner_file)
        index_corner_vertice = bsddb.btopen(index_corner_vertice_file)
        index_clusters = bsddb.btopen(index_clusters_file)

        cfile.write("edge vertex: %d\n" % lr.mr)
        cfile.write("vertex: %d\n" % lr.m)
        cfile.write("triangles: %d\n" % lr.number_triangles)

        for i, cluster in enumerate(clusters):
            #cfile.write("Cluster %d\n" % i)
            init_cluster = cfile.tell()
            
            minv, maxv = 2**32, -1
            minc, maxc = 2**32, -1
            mincv, maxcv = 2**32, -1

            for elem in cluster:
                if elem[0] == 'v':
                    if elem[1] < lr.mr:
                        maxv = max(elem[1], maxv)
                        minv = min(elem[1], minv)
                    else:
                        index_isolated_vertices[str(elem[1])] = str(i)
                elif elem[0] == 'V':
                    index_corners[str(elem[1])] = str(i)

                elif elem[0] == 'C':
                    #maxcv = max(elem[1], maxcv)
                    #mincv = min(elem[1], mincv)
                    index_corner_vertice[str(elem[1])] = str(i)

                #cfile.write(" ".join([str(e) for e in elem]) + "\n")
                try:
                    cfile.write(struct.pack(STRUCT_FORMATS[elem[0]], *elem))
                except struct.error, e:
                    print elem
                    print STRUCT_FORMATS[elem[0]]
                    print e
                    sys.exit()
            cluster_size = cfile.tell() - init_cluster

            if maxv > -1:
                index_vertices[str(maxv)] = str(i)
                
            #if maxc > -1:
                #index_corners[str(maxc)] = str(i)

            #if maxcv > -1:
                #index_corner_vertice[str(maxcv)] = str(i)

            index_clusters[str(i)] = "%d %d %d %d" % (init_cluster,
                                                             cluster_size,
                                                             minv,
                                                             maxv)




def update_cluster_usage_lrfu(clmrg, cl_key):
    try:
        clmrg.cl_usage[cl_key]['crf'] = 1.0 + 2.0 ** (-clmrg.lbd) * clmrg.cl_usage[cl_key]['crf'] 
    except KeyError:
        clmrg.cl_usage[cl_key] = {'crf': 0}
        clmrg.cl_usage[cl_key]['crf'] = 1.0 + 2.0 ** (-clmrg.lbd) * clmrg.cl_usage[cl_key]['crf'] 

    for cl in clmrg.cl_usage:
        if cl != cl_key:
            clmrg.cl_usage[cl]['crf'] = 2 ** (-clmrg.lbd) * clmrg.cl_usage[cl]['crf']


def update_cluster_usage_lrfu2(clmrg, cl_key):
    f = lambda x, p: (1.0/p)**(x*clmrg.lbd)
    clu = clmrg.cl_usage
    try:
        cluk = clu[cl_key]
        cluk['crf'] = f(0, 2) + f(clmrg.timestamp - cluk['timestamp'], 2) * clu[cl_key]['crf']
        cluk['timestamp'] = clmrg.timestamp
    except:
        clu[cl_key]= {'crf': f(0, 2), 
                      'timestamp': clmrg.timestamp,}

    clmrg.timestamp += 1


class ArcItem(object):
    def __init__(self):
        self.value = -1
        self.bit = 0
        self.filter = "S"

    def __cmp__(self, o):
        try:
            return self.value.__cmp__(o)
        except TypeError:
            return self.value.__cmp__(o.value)

    def __repr__(self):
        return "%s" % self.value


class CarCache(object):
    def __init__(self, cache_size):
        self.cache_size = cache_size
        self.T1 = Ring([])
        self.T2 = Ring([])
        self.B1 = Ring([])
        self.B2 = Ring([])
        self.p = 0

    def update_usage(self, clmrg, cl):
        clmrg.cl_usage[cl] = 1
        cl = int(cl)
        T1 = self.T1
        T2 = self.T2
        B1 = self.B1
        B2 = self.B2
        found = 1
        try:
            idx = T1.index(cl)
            T1[idx].bit = 1
        except ValueError:
            try:
                idx = T2.index(cl)
                T2[idx].bit = 1
            except ValueError:
                found = 0

        if not found:
            if len(T1) + len(T2) == self.cache_size:
                if (cl not in B1) and (cl not in B2) \
                   and (len(T1) + len(B1) == self.cache_size):
                    try:
                        B1.pop()
                    except IndexError:
                        pass
                elif (len(T1) + len(T2) + len(B1) + len(B2) == 2*self.cache_size) \
                   and (cl not in B1) and (cl not in B2):
                    try:
                        B2.pop()
                    except IndexError:
                        pass

            found = 1
            try:
                idx = B1.index(cl)
                self.p = min(self.p + max(1, len(B2)/len(B1)), self.cache_size)
                item = B1.pop(idx)
                item.bit = 0
                T2.append(item)
                #self.p = min(self.p+max(1, len([i for i in B2 if i not in B1])),
                #            self.cache_size)

            except ValueError:
                try:
                    idx = B2.index(cl)
                    self.p = max(self.p - max(1, len(B1)/len(B2)), 0)
                    item = B2.pop(idx)
                    item.bit = 0
                    T2.append(item)
                    #self.p = min(self.p+max(1, len([i for i in B1 if i not in B2])),
                                 #self.cache_size)
                except ValueError:
                    item = ArcItem()
                    item.value = cl
                    item.bit = 0
                    T1.append(item)

    def replace(self, cl_usage):
        T1 = self.T1
        T2 = self.T2
        B1 = self.B1
        B2 = self.B2
        p = self.p
        found = 0
        item = -1
        while 1:
            if len(T1) >= max(1, p):
                head = T1.pop(0)
                if not head.bit:
                    found = 1
                    item = head.value
                    B1.insert(0, head)
                else:
                    head.bit = 0
                    T2.append(head)
            else:
                head = T2.pop(0)
                if not head.bit:
                    found = 1
                    item = head.value
                    B2.insert(0, head)
                else:
                    head.bit = 0
                    T2.append(head)
            if found:
                break

        return item


class CarTCache(object):
    def __init__(self, cache_size):
        self.cache_size = cache_size
        self.T1 = Ring([])
        self.T2 = Ring([])
        self.B1 = Ring([])
        self.B2 = Ring([])
        self.p = 0
        self.q = 0
        self.ns = 0
        self.nl = 0

    def update_usage(self, clmrg, cl):
        clmrg.cl_usage[cl] = 1
        cl = int(cl)
        T1 = self.T1
        T2 = self.T2
        B1 = self.B1
        B2 = self.B2
        found = 1
        try:
            idx = T1.index(cl)
            T1[idx].bit = 1
        except ValueError:
            try:
                idx = T2.index(cl)
                T2[idx].bit = 1
            except ValueError:
                found = 0

        if not found:
            if len(T1) + len(T2) == self.cache_size:
                if (cl not in B1) and (cl not in B2) \
                   and (len(B1) + len(B2) == self.cache_size + 1) \
                   and ((len(B1) > max(0, self.q)) or (len(B2) ==0)):

                    try:
                        B1.pop()
                    except IndexError:
                        pass

                elif (cl not in B1) and (cl not in B2) \
                   and (len(B1) + len(B2) == self.cache_size + 1):

                    try:
                        B2.pop()
                    except IndexError:
                        pass

            found = 1

            try:
                idx = B1.index(cl)
                self.p = min(self.p + max(1, self.ns/len(B1)), self.cache_size)
                item = B1.pop(idx)
                item.bit = 0
                item.filter = "L"
                T1.append(item)

                self.nl += 1
                #self.p = min(self.p+max(1, len([i for i in B2 if i not in B1])),
                #            self.cache_size)

            except ValueError:
                try:
                    idx = B2.index(cl)
                    self.p = max(self.p - max(1, self.nl/len(B2)), 0)
                    item = B2.pop(idx)
                    item.bit = 0
                    T1.append(item)

                    self.nl += 1
                    #self.p = min(self.p+max(1, len([i for i in B1 if i not in B2])),
                                 #self.cache_size)

                    if len(T2) + len(B2) + len(T1) - self.ns >= self.cache_size:
                        self.q = min(self.q + 1, 2*self.cache_size - len(T1))

                except ValueError:
                    item = ArcItem()
                    item.value = cl
                    item.bit = 0
                    item.filter = "S"
                    T1.append(item)

                    self.ns += 1

    def replace(self, cl_usage):
        T1 = self.T1
        T2 = self.T2
        B1 = self.B1
        B2 = self.B2
        p = self.p
        found = 0
        item = -1

        while len(T2) and T2.first().bit:
            head = T2.pop(0)
            head.bit = 0
            T1.append(head)

            if len(T2) + len(B2) + len(T1) - self.ns >= self.cache_size:
                self.q = min(self.q + 1, 2*self.cache_size - len(T1))

        while len(T1) and (T1.first().filter == "L" or T1.first().bit == 1):
            if T1.first().bit:
                head = T1.pop(0)
                head.bit = 0
                T1.append(head)
                if (len(T1) >= min(self.p + 1, len(B1))) and (head.filter == "S"):
                    head.filter = "L"
                    self.ns -= 1
                    self.nl += 1
            else:
                head = T1.pop(0)
                head.bit = 0
                T2.append(head)
                self.q = max(self.q - 1, self.cache_size - len(T1))

        if len(T1) >= max(1, self.p):
            head = T1.pop(0)
            head.bit = 0
            B1.insert(0, head)
            self.ns -= 1
        else:
            head = T2.pop(0)
            head.bit = 0
            B2.insert(0, head)
            self.nl -= 1

        return head.value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', help="create the clusters", action="store_true")
    parser.add_argument('-o', help="open the clusters and runs taubin smoothing in it", action="store_true")
    parser.add_argument('-p', help="open the clusters and save it in ply format file",action="store_true")
    parser.add_argument('-r', help="open the clusters and access it in random way",action="store_true")
    parser.add_argument('-d', default=False, action="store_true", help="show stastic in the end")
    parser.add_argument('-m', default=False, action="store_true", help="show stastic in the end about hit and misses")
    parser.add_argument('-s', default=1000, type=int)
    parser.add_argument('-l', default=0.7, type=float)
    parser.add_argument('-a', choices=("lru", "lu", "mru", "mu", "random",
                                       "lrfu", "lrfu2", "car", "cart"), default="lru")
    parser.add_argument('input')
    parser.add_argument('output')

    args = parser.parse_args()
    
    algorithms = {"lru": lru,
                  "lu": lu,
                  "mru": mru,
                  "mu": mu,
                  "random": randomized,
                  "lrfu": lrfu,
                  "lrfu2": lrfu,
                  "car": randomized
                  }

    if args.c:
        vertices, faces = laced_ring.read_ply(args.input)
        vertices_faces = laced_ring.make_vertex_faces(vertices, faces)

        # Corner table
        ct = cy_corner_table.CornerTable()
        ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)

        # edge ring
        ncluster, m_t, edge_ring = laced_ring.expand_ring(ct)

        # Laced Ring
        lr = laced_ring.LacedRing()
        lr.make_lr(ct, edge_ring)

        # clusters
        clusters = create_clusters(lr, args.s)
        save_clusters(lr, clusters, args.output)

    elif args.o:
        if args.a == 'lrfu':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu)
        elif args.a == 'lrfu2':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu2)
        elif args.a == 'cart':
            cart = CarTCache(args.s)
            clmrg = ClusterManager(args.input, args.s, cart.replace,
                                   args.l,upd_cl_us=cart.update_usage)
            cart.cache_size = clmrg.queue_size
        elif args.a == 'car':
            car = CarCache(args.s)
            clmrg = ClusterManager(args.input, args.s, car.replace,
                                   args.l,upd_cl_us=car.update_usage)
            car.cache_size = clmrg.queue_size
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)
        cl_lr = ClusteredLacedRing(clmrg)
        #cl_lr.to_vertices_faces()

        #for i in xrange(cl_lr.mr):
            #print i, cl_lr.get_vertex_coord(i)
            #print cl_lr.L[i], cl_lr.get_vertex_coord(cl_lr.L[i][0])
            #print cl_lr.R[i], cl_lr.get_vertex_coord(cl_lr.R[i][0])

        #print "Triangles", cl_lr.number_triangles
        #for t in xrange(cl_lr.number_triangles):
            #c0 = cl_lr.corner_triangle(t)
            #c1 = cl_lr.next_corner(c0)
            #c2 = cl_lr.next_corner(c1)

            ##print t, cl_lr.vertex(c0),cl_lr.vertex(c1),cl_lr.vertex(c2)

        taubin_smooth(cl_lr, 0.5, -0.53, 1)


        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()

    elif args.p:
        if args.a == 'lrfu':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu)
        elif args.a == 'lrfu2':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu2)
        elif args.a == 'car':
            car = CarCache(args.s)
            clmrg = ClusterManager(args.input, args.s, car.replace,
                                   args.l,upd_cl_us=car.update_usage)
            car.cache_size = clmrg.queue_size
        elif args.a == 'cart':
            cart = CarTCache(args.s)
            clmrg = ClusterManager(args.input, args.s, cart.replace,
                                   args.l,upd_cl_us=cart.update_usage)
            cart.cache_size = clmrg.queue_size
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)
        cl_lr = ClusteredLacedRing(clmrg)
        
        writer = ply_writer.PlyWriter(args.output)
        writer.from_laced_ring(cl_lr)

        wr = ply_writer.PlyWriter('/tmp/ring.ply')
        wr.from_laced_ring_save_ring(cl_lr)

        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()

    elif args.r:
        if args.a == 'lrfu':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], upd_cl_us=update_cluster_usage_lrfu)
        elif args.a == 'lrfu2':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu2)
        elif args.a == 'car':
            car = CarCache(args.s)
            clmrg = ClusterManager(args.input, args.s, car.replace,
                                   args.l,upd_cl_us=car.update_usage)
            car.cache_size = clmrg.queue_size
        elif args.a == 'cart':
            cart = CarTCache(args.s)
            clmrg = ClusterManager(args.input, args.s, cart.replace,
                                   args.l,upd_cl_us=cart.update_usage)
            cart.cache_size = clmrg.queue_size
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)

        cl_lr = ClusteredLacedRing(clmrg)

        if os.path.isfile(args.output):
            access_vertex_from_files(cl_lr, args.output)
        else:
            random_access(cl_lr, int(args.output))

        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()

if __name__ == '__main__':
    RUNNING = 1
    main()
    RUNNING = 0
