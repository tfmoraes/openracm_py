import argparse
import bisect
import bsddb
import collections
import colorsys
import copy
import io
import math
import mmap
import os
import cPickle
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

from sarc_cache import SarcCache
from sarcm_cache import SarcMeshCache
from sarcm2_cache import SarcMesh2Cache

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
    def __init__(self, filename, qsize=10, scd_policy=lru, lbd=0.7,
                 upd_cl_us=None, load_cluster=None):
        self.filename = filename
        self.scd_policy = scd_policy
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_isolated_vertices_file = os.path.splitext(filename)[0] + '_iv.hdr'
        index_corner_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_corner_vertice_file = os.path.splitext(filename)[0] + '_cv.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_cl.hdr'
        map_cluster_dependency_fname = os.path.splitext(filename)[0] + '.map'
        self.index_vertices = bsddb.btopen(index_vertices_file)
        self.index_isolated_vertices = bsddb.btopen(index_isolated_vertices_file)
        self.index_corners = bsddb.btopen(index_corner_file)
        self.index_corner_vertice = bsddb.btopen(index_corner_vertice_file)
        self.index_clusters = bsddb.btopen(index_clusters_file)

        map_cluster_dependency_file = open(map_cluster_dependency_fname, 'r+b')
        self.map_cluster_dependency = cPickle.load(map_cluster_dependency_file)
        map_cluster_dependency_file.close()

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

        self.to_bench = False

        self.colour = 0

        self.to_clean = None

        self._vertices = {}
        self._L = {}
        self._R = {}
        self._O = {}
        self._V = {}
        self._C = {}
        self._VOs = {}

        self.vertices = _DictGeomElemVertex(self, 'vertices', self._vertices)
        self.L = _DictGeomElemVertex(self, 'L', self._L)
        self.R = _DictGeomElemVertex(self, 'R', self._R)
        self.O = _DictGeomElemCorners(self, 'O', self._O)
        self.V = _DictGeomElemCorners(self, 'V', self._V)
        self.C = _DictGeomElemVertexCluster(self, 'C', self._C)
        self.VOs = _DictGeomElemVertex(self, 'VOs', self._VOs)

        if upd_cl_us is None:
            self.update_cluster_usage = self._update_cluster_usage
        else:
            self.update_cluster_usage = types.MethodType(upd_cl_us, self)

        if load_cluster is None:
            self.load_cluster = self._load_cluster
        else:
            self.load_cluster = lambda cl: load_cluster(self, cl)


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
                del self._vertices[k]
                del self._L[k]
                del self._R[k]
                del self._VOs[k]
                del self._O[k]
                del self._V[k]
                del self._C[k]

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
    def _load_cluster(self, cl):

        #self.wait.acquire()
        if len(self.cl_usage) >= self.queue_size:
            #print "The queue is full"
            k = str(self.scd_policy(self.cl_usage))
            self.to_clean = k
        #self.wait.release()
            del self.cl_usage[k]
            del self._vertices[k]
            del self._L[k]
            del self._R[k]
            del self._VOs[k]
            del self._O[k]
            del self._V[k]
            del self._C[k]

            self.last_removed = k

            if k == self.last_loaded:
                self.wastings.append(k)

            try:
                self._n_unload_clusters[k] += 1
            except KeyError:
                self._n_unload_clusters[k] = 1

        if self.to_bench:
            vertices, L, R, VOs, V, C, O = range(7)
        else:
            init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
            self.cfile.seek(init_cluster)
            str_cluster = self.cfile.read(cluster_size)

            vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

        self._vertices[cl] = vertices
        self._L[cl] = L
        self._R[cl] = R
        self._VOs[cl] = VOs
        self._V[cl] = V
        self._C[cl] = C
        self._O[cl] = O

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
        
    def bench(self, filename):
        self.to_bench = True
        with open(filename) as f:
            self.misses = 0
            self.access = 0
            for l in f:
                cl = l.strip()
                if cl:
                    if cl not in self.cl_usage:
                        self.load_cluster(cl)
                    else:
                        self.hits += 1
                    self.update_cluster_usage(cl)
                    self.access += 1


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
                print type(cl), type(key)
                #print _clmrg.iv_keys
                #print _clmrg.index_vertices
                print self._elems.keys()
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

def save_clusters(lr, clusters, csize, filename):
    with file(filename, 'w') as cfile:
        # indexes
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_isolated_vertices_file = os.path.splitext(filename)[0] + '_iv.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_cl.hdr'
        index_corner_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_corner_vertice_file = os.path.splitext(filename)[0] + '_cv.hdr'
        map_cluster_dependency_fname = os.path.splitext(filename)[0] + '.map'
        index_vertices = bsddb.btopen(index_vertices_file)
        index_isolated_vertices = bsddb.btopen(index_isolated_vertices_file)
        index_corners = bsddb.btopen(index_corner_file)
        index_corner_vertice = bsddb.btopen(index_corner_vertice_file)
        index_clusters = bsddb.btopen(index_clusters_file)
        map_cluster_dependency = {}

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

                elif elem[0] in ('L', 'R'):
                    print ">>>", elem[1], csize, i
                    if elem[1] / csize != i:
                        try:
                            map_cluster_dependency[i].add(elem[1] / csize)
                        except KeyError:
                            map_cluster_dependency[i] = set((elem[1] / csize,))


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

        # Saving map_cluster_depency as a dict in a cPickle
        map_cluster_dependency_file = open(map_cluster_dependency_fname, 'w+b')
        cPickle.dump(map_cluster_dependency, map_cluster_dependency_file)
        map_cluster_dependency_file.flush()
        map_cluster_dependency_file.close()




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


class MCItem(object):
    def __init__(self):
        self.value = -1
        self.bit = 0

    def __cmp__(self, o):
        try:
            return self.value.__cmp__(o)
        except TypeError:
            return self.value.__cmp__(o.value)

    def __repr__(self):
        return "%s" % self.value

class MeshStrideCache(object):
    def __init__(self, cache_size, size_pf):
        self.cache_size = cache_size
        self.size_pf = size_pf
        self.timestamp = 0
        self.cl_usage = {}
        self.C1 = Ring([])
        self.C2 = {}

    def update_usage(self, clmrg, cl):
        clmrg.cl_usage[cl] = 1
        cl = int(cl)
        self.timestamp += 1
        C1 = self.C1
        C2 = self.C2
        try:
            idx = C1.index(cl)
            C1[idx].bit = 1
        except ValueError:
            try:
                C2[cl]['timestamp'] = self.timestamp
            except KeyError:
                C2[cl] = {'timestamp': self.timestamp,}

    def replace(self, cl_usage):
        C2 = self.C2
        try:
            k = min(C2, key=lambda x: C2[x]['timestamp'])
        except ValueError:
            print C2
            print self.cache_size
            sys.exit()
        return k

    def replace_prefetch(self, pf):
        C1 = self.C1
        if len(pf) > self.size_pf:
            k = []
            while C1:
                item = C1.pop(0)
                k.append(item)
            return k
        elif len(pf) + len(C1) > self.size_pf:
            s = len(pf) + len(C1) - self.size_pf
            t = 0
            k = []

            while t < s:
                item = C1.pop(0)
                if not item.bit:
                    k.append(item)
                    t += 1
                else:
                    item.bit = 0
                    C1.append(item)
            return k
        else:
            return []
    
    def load_cluster(self, clmrg, cl):
        #self.wait.acquire()
        if len(self.C2) >= self.cache_size:
            #print "The queue is full"
            k = str(clmrg.scd_policy(self.cl_usage))
            clmrg.to_clean = k
        #self.wait.release()
            try:
                del clmrg.cl_usage[k]
                del self.C2[int(k)]
            except KeyError, e:
                print "======================================="
                print k
                print e
                print clmrg.cl_usage.keys()
                print clmrg._vertices.keys()
                print self.C2
                print "======================================="
                sys.exit()
            
            del clmrg._vertices[k]
            del clmrg._L[k]
            del clmrg._R[k]
            del clmrg._VOs[k]
            del clmrg._O[k]
            del clmrg._V[k]
            del clmrg._C[k]
            

            clmrg.last_removed = k

            if k == clmrg.last_loaded:
                clmrg.wastings.append(k)

            try:
                clmrg._n_unload_clusters[k] += 1
            except KeyError:
                clmrg._n_unload_clusters[k] = 1


        icl = int(cl)
        
        if icl in clmrg.map_cluster_dependency:
            deps = clmrg.map_cluster_dependency[icl]
            dists = {i-icl: i for i in deps}
            load = [icl]
            ldps = []
            for i in xrange(-1, -len(dists), -1):
                if i not in dists:
                    break
                load.append(dists[i])
                ldps.append(dists[i])

            for i in xrange(1, len(dists)):
                if i not in dists:
                    break
                load.append(dists[i])
                ldps.append(dists[i])
    
            
            load.sort()

            if len(load) > 1:
                init_cluster0, cluster_size0, iface0, eface0 = [int(i) for i in
                                                                clmrg.index_clusters[str(load[0])].split()]
                init_cluster1, cluster_size1, iface1, eface1 = [int(i) for i in
                                                                clmrg.index_clusters[str(load[-1])].split()]
                clmrg.cfile.seek(init_cluster0)
                str_cluster = clmrg.cfile.read((init_cluster1 - init_cluster0) + cluster_size1)
            else:
                init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
                clmrg.cfile.seek(init_cluster)
                str_cluster = clmrg.cfile.read(cluster_size)

            to_replace = self.replace_prefetch(ldps)
            for r in to_replace:
                r = str(r.value)
                del clmrg._vertices[r]
                del clmrg._L[r]
                del clmrg._R[r]
                del clmrg._VOs[r]
                del clmrg._O[r]
                del clmrg._V[r]
                del clmrg._C[r]

            ldps = []
            init = 0
            for c in load:
                str_c = str(c)
                init_cluster, cluster_size, iface, eface = [int(i) for i in
                                                            clmrg.index_clusters[str_c].split()]
                scluster = str_cluster[init: init + cluster_size]
                init += cluster_size

                vertices, L, R, VOs, V, C, O = cluster_loader(scluster)


                if str_c not in clmrg._L:
                    clmrg._vertices[str_c] = vertices
                    clmrg._L[str_c] = L
                    clmrg._R[str_c] = R
                    clmrg._VOs[str_c] = VOs
                    clmrg._V[str_c] = V
                    clmrg._C[str_c] = C
                    clmrg._O[str_c] = O

                    if c != icl:
                        item = MCItem()
                        item.value = c
                        item.bit = 0

                        self.C1.append(item)

        else:
            init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
            clmrg.cfile.seek(init_cluster)
            str_cluster = clmrg.cfile.read(cluster_size)

            vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

            clmrg._vertices[cl] = vertices
            clmrg._L[cl] = L
            clmrg._R[cl] = R
            clmrg._VOs[cl] = VOs
            clmrg._V[cl] = V
            clmrg._C[cl] = C
            clmrg._O[cl] = O

        try:
            clmrg._n_load_clusters[cl] += 1
        except KeyError:
            clmrg._n_load_clusters[cl] = 1
            clmrg._n_unload_clusters[cl] = 0

        clmrg.last_loaded = cl
        if clmrg.last_removed == cl:
            clmrg.wastings.append(cl)

        clmrg.misses += 1

        if int(cl) in clmrg.map_cluster_dependency:
            dps = clmrg.map_cluster_dependency[int(cl)]
            ldps = []
            for dp in dps:
                dp = str(dp)
                if dp not in clmrg._L:
                    ldps.append(dp)

                if len(ldps) == self.size_pf:
                    break
            
            to_replace = self.replace_prefetch(ldps)
            cc1 = copy.deepcopy(self.C1)
            for r in to_replace:
                r = str(r.value)
                try:
                    del clmrg._vertices[r]
                except KeyError, e:
                    print "Vertices"
                    print clmrg._vertices.keys()
                    print clmrg._L.keys()
                    print "C1", cc1
                    print "C2", self.C2, clmrg.queue_size, self.cache_size, self.size_pf
                    print "LDPS", ldps
                    print "To Replace", to_replace
                    print r, type(r)
                    print e
                    print ldps
                    sys.exit()
                del clmrg._L[r]
                del clmrg._R[r]
                del clmrg._VOs[r]
                del clmrg._O[r]
                del clmrg._V[r]
                del clmrg._C[r]

            for dp in ldps:
                dp = str(dp)
                init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[dp].split()]
                clmrg.cfile.seek(init_cluster)
                str_cluster = clmrg.cfile.read(cluster_size)

                vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

                clmrg._vertices[dp] = vertices
                clmrg._L[dp] = L
                clmrg._R[dp] = R
                clmrg._VOs[dp] = VOs
                clmrg._V[dp] = V
                clmrg._C[dp] = C
                clmrg._O[dp] = O

                item = MCItem()
                item.value = int(dp)
                item.bit = 0

                self.C1.append(item)


class MeshCache(object):
    def __init__(self, cache_size, size_pf):
        self.cache_size = cache_size
        self.size_pf = size_pf
        self.timestamp = 0
        self.cl_usage = {}
        self.C1 = Ring([])
        self.C2 = {}

    def update_usage(self, clmrg, cl):
        clmrg.cl_usage[cl] = 1
        cl = int(cl)
        self.timestamp += 1
        C1 = self.C1
        C2 = self.C2
        try:
            idx = C1.index(cl)
            C1[idx].bit = 1
        except ValueError:
            try:
                C2[cl]['timestamp'] = self.timestamp
            except KeyError:
                C2[cl] = {'timestamp': self.timestamp,}

    def replace(self, cl_usage):
        C2 = self.C2
        try:
            k = min(C2, key=lambda x: C2[x]['timestamp'])
        except ValueError:
            print C2
            print self.cache_size
            sys.exit()
        return k

    def replace_prefetch(self, pf):
        C1 = self.C1
        if len(pf) > self.size_pf:
            k = []
            while C1:
                item = C1.pop(0)
                k.append(item)
            return k
        elif len(pf) + len(C1) > self.size_pf:
            s = len(pf) + len(C1) - self.size_pf
            t = 0
            k = []

            while t < s:
                item = C1.pop(0)
                if not item.bit:
                    k.append(item)
                    t += 1
                else:
                    item.bit = 0
                    C1.append(item)
            return k
        else:
            return []
    
    def load_cluster(self, clmrg, cl):
        #self.wait.acquire()
        if len(self.C2) >= self.cache_size:
            #print "The queue is full"
            k = str(clmrg.scd_policy(self.cl_usage))
            clmrg.to_clean = k
        #self.wait.release()
            try:
                del clmrg.cl_usage[k]
                del self.C2[int(k)]
            except KeyError, e:
                print "======================================="
                print k
                print e
                print clmrg.cl_usage.keys()
                print clmrg._vertices.keys()
                print self.C2
                print "======================================="
                sys.exit()
            
            del clmrg._vertices[k]
            del clmrg._L[k]
            del clmrg._R[k]
            del clmrg._VOs[k]
            del clmrg._O[k]
            del clmrg._V[k]
            del clmrg._C[k]
            

            clmrg.last_removed = k

            if k == clmrg.last_loaded:
                clmrg.wastings.append(k)

            try:
                clmrg._n_unload_clusters[k] += 1
            except KeyError:
                clmrg._n_unload_clusters[k] = 1

        init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
        clmrg.cfile.seek(init_cluster)
        str_cluster = clmrg.cfile.read(cluster_size)

        vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

        clmrg._vertices[cl] = vertices
        clmrg._L[cl] = L
        clmrg._R[cl] = R
        clmrg._VOs[cl] = VOs
        clmrg._V[cl] = V
        clmrg._C[cl] = C
        clmrg._O[cl] = O

        try:
            clmrg._n_load_clusters[cl] += 1
        except KeyError:
            clmrg._n_load_clusters[cl] = 1
            clmrg._n_unload_clusters[cl] = 0

        clmrg.last_loaded = cl
        if clmrg.last_removed == cl:
            clmrg.wastings.append(cl)

        clmrg.misses += 1

        if int(cl) in clmrg.map_cluster_dependency:
            dps = clmrg.map_cluster_dependency[int(cl)]
            ldps = []
            for dp in dps:
                dp = str(dp)
                if dp not in clmrg._L:
                    ldps.append(dp)

                if len(ldps) == self.size_pf:
                    break
            
            to_replace = self.replace_prefetch(ldps)
            cc1 = copy.deepcopy(self.C1)
            for r in to_replace:
                r = str(r.value)
                try:
                    del clmrg._vertices[r]
                except KeyError, e:
                    print "Vertices"
                    print clmrg._vertices.keys()
                    print clmrg._L.keys()
                    print "C1", cc1
                    print "C2", self.C2, clmrg.queue_size, self.cache_size, self.size_pf
                    print "LDPS", ldps
                    print "To Replace", to_replace
                    print r, type(r)
                    print e
                    print ldps
                    sys.exit()
                del clmrg._L[r]
                del clmrg._R[r]
                del clmrg._VOs[r]
                del clmrg._O[r]
                del clmrg._V[r]
                del clmrg._C[r]

            for dp in ldps:
                dp = str(dp)
                init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[dp].split()]
                clmrg.cfile.seek(init_cluster)
                str_cluster = clmrg.cfile.read(cluster_size)

                vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

                clmrg._vertices[dp] = vertices
                clmrg._L[dp] = L
                clmrg._R[dp] = R
                clmrg._VOs[dp] = VOs
                clmrg._V[dp] = V
                clmrg._C[dp] = C
                clmrg._O[dp] = O

                item = MCItem()
                item.value = int(dp)
                item.bit = 0

                self.C1.append(item)


class LRUPFCach(object):
    def __init__(self, cache_size):
        self.cache_size = cache_size
        self.lru = []

    def update_usage(self, clmrg, cl):
        cl = int(cl)
        try:
            i = self.lru.index(cl)
        except ValueError, e:
            print self.lru
            print "ERROR", e
            sys.exit()

        self.lru.pop(i)
        self.lru.insert(0, cl)

    def replace(self, cl_usage):
        return self.lru.pop()

    def load_cluster(self, clmrg, cl):
        icl = int(cl)
        if len(self.lru) >= self.cache_size:
            k = str(clmrg.scd_policy(None))
            del clmrg._vertices[k]
            del clmrg._L[k]
            del clmrg._R[k]
            del clmrg._VOs[k]
            del clmrg._O[k]
            del clmrg._V[k]
            del clmrg._C[k]

            clmrg.last_removed = k

            if k == clmrg.last_loaded:
                clmrg.wastings.append(k)

            try:
                clmrg._n_unload_clusters[k] += 1
            except KeyError:
                clmrg._n_unload_clusters[k] = 1

        if icl in clmrg.map_cluster_dependency:
            deps = clmrg.map_cluster_dependency[icl]
            load = [icl, ]
            for i in xrange(icl - 1, icl - len(deps), -1):
                if i not in deps:
                    break
                load.append(i)

            for i in xrange(icl + 1, icl + len(deps), 1):
                if i not in deps:
                    break
                load.append(i)

            load.sort()


            if len(load) > 1:
                init_cluster0, cluster_size0, iface0, eface0 = [int(i) for i in
                                                                clmrg.index_clusters[str(load[0])].split()]
                init_cluster1, cluster_size1, iface1, eface1 = [int(i) for i in
                                                                clmrg.index_clusters[str(load[-1])].split()]
                clmrg.cfile.seek(init_cluster0)
                str_cluster = clmrg.cfile.read((init_cluster1 - init_cluster0) + cluster_size1)

            else:
                init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
                clmrg.cfile.seek(init_cluster)
                str_cluster = clmrg.cfile.read(cluster_size)

            init = 0
            for c in load:
                str_c = str(c)
                init_cluster, cluster_size, iface, eface = [int(i) for i in
                                                            clmrg.index_clusters[str_c].split()]
                scluster = str_cluster[init: init + cluster_size]
                init += cluster_size

                vertices, L, R, VOs, V, C, O = cluster_loader(scluster)
                
                if str_c not in clmrg._L:
                    clmrg._vertices[str_c] = vertices
                    clmrg._L[str_c] = L
                    clmrg._R[str_c] = R
                    clmrg._VOs[str_c] = VOs
                    clmrg._V[str_c] = V
                    clmrg._C[str_c] = C
                    clmrg._O[str_c] = O

                    if c != icl:
                        if len(self.lru) >= self.cache_size:
                            k = str(clmrg.scd_policy(None))
                            del clmrg._vertices[k]
                            del clmrg._L[k]
                            del clmrg._R[k]
                            del clmrg._VOs[k]
                            del clmrg._O[k]
                            del clmrg._V[k]
                            del clmrg._C[k]

                        self.lru.append(c)
                    else:
                        self.lru.insert(0, c)

        else:
            init_cluster, cluster_size, iface, eface = [int(i) for i in clmrg.index_clusters[cl].split()]
            clmrg.cfile.seek(init_cluster)
            str_cluster = clmrg.cfile.read(cluster_size)

            vertices, L, R, VOs, V, C, O = cluster_loader(str_cluster)

            clmrg._vertices[cl] = vertices
            clmrg._L[cl] = L
            clmrg._R[cl] = R
            clmrg._VOs[cl] = VOs
            clmrg._V[cl] = V
            clmrg._C[cl] = C
            clmrg._O[cl] = O

            self.lru.insert(0, icl)

        try:
            clmrg._n_load_clusters[cl] += 1
        except KeyError:
            clmrg._n_load_clusters[cl] = 1
            clmrg._n_unload_clusters[cl] = 0

        clmrg.last_loaded = cl
        if clmrg.last_removed == cl:
            clmrg.wastings.append(cl)

        clmrg.misses += 1

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
    parser.add_argument('-b', help="Only a bench",action="store_true")
    parser.add_argument('-r', help="open the clusters and access it in random way",action="store_true")
    parser.add_argument('-d', default=False, action="store_true", help="show stastic in the end")
    parser.add_argument('-m', default=False, action="store_true", help="show stastic in the end about hit and misses")
    parser.add_argument('-s', default=1000, type=int)
    parser.add_argument('-l', default=0.7, type=float)
    parser.add_argument('-a', choices=("lru", "lu", "mru", "mu", "random",
                                       "lrfu", "lrfu2", "car", "cart", "pf",
                                       "pf2", "lrupf", "sarc", "sarcm", "sarcm2"), default="lru")
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
                  "car": randomized,
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
        save_clusters(lr, clusters, args.s, args.output)

    elif args.o:
        if args.a == 'lrfu':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu)
        elif args.a == 'lrfu2':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l,upd_cl_us=update_cluster_usage_lrfu2)
        elif args.a == 'pf':
            mc = MeshCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))
        elif args.a == 'pf2':
            mc = MeshStrideCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))

        elif args.a == 'lrupf':
            c = LRUPFCach(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

        elif args.a == 'sarc':
            c = SarcCache(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

        elif args.a == 'sarcm':
            c = SarcMeshCache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
        elif args.a == 'sarcm2':
            c = SarcMesh2Cache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

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
        elif args.a == 'pf':
            mc = MeshCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))
        elif args.a == 'pf2':
            mc = MeshStrideCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))
        elif args.a == 'lrupf':
            c = LRUPFCach(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
        elif args.a == 'sarc':
            c = SarcCache(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

        elif args.a == 'sarcm':
            c = SarcMeshCache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
        elif args.a == 'sarcm2':
            c = SarcMesh2Cache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

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
        elif args.a == 'pf':
            mc = MeshCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))
        elif args.a == 'pf2':
            mc = MeshStrideCache(args.s, 0)
            clmrg = ClusterManager(args.input, args.s, mc.replace,
                                   args.l,upd_cl_us=mc.update_usage,
                                   load_cluster=mc.load_cluster)
            mc.cache_size = int(math.floor(clmrg.queue_size * 0.9))
            mc.size_pf = int(math.floor(clmrg.queue_size * 0.1))
            clmrg.queue_size = int(math.floor(clmrg.queue_size * 0.9))
        elif args.a == 'lrupf':
            c = LRUPFCach(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
        elif args.a == 'sarc':
            c = SarcCache(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

        elif args.a == 'sarcm':
            c = SarcMeshCache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
        elif args.a == 'sarcm2':
            c = SarcMesh2Cache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size

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

    elif args.b:
        print args.output
        if args.a == 'sarcm2':
            c = SarcMesh2Cache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
            c.bench(clmrg, args.output)
        elif args.a == 'sarcm':
            c = SarcMeshCache(args.s, args.l)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
            c.bench(clmrg, args.output)
        elif args.a == 'sarc':
            c = SarcCache(args.s)
            clmrg = ClusterManager(args.input, args.s, c.replace,
                                   args.l,upd_cl_us=c.update_usage,
                                   load_cluster=c.load_cluster)
            c.cache_size = clmrg.queue_size
            c.bench(clmrg, args.output)
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)
            cl_lr = ClusteredLacedRing(clmrg)
            clmrg.bench(args.output)
        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()

if __name__ == '__main__':
    RUNNING = 1
    main()
    RUNNING = 0
