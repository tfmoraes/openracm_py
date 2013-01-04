import argparse
import bisect
import bsddb
import colorsys
import math
import os
import random
import signal
import sys
import types

import numpy as np

import cy_corner_table
import laced_ring
import ply_reader
import ply_writer

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



class ClusterManager(object):
    def __init__(self, filename, qsize, scd_policy, lbd=0.7, upd_cl_us=None):
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

        self.cfile = open(filename)
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

        self.__vertices = {}
        self.__L = {}
        self.__R = {}
        self.__O = {}
        self.__V = {}
        self.__C = {}
        self.__VOs = {}

        self.vertices = _DictGeomElem(self, 'vertices', self.__vertices)
        self.L = _DictGeomElem(self, 'L', self.__L)
        self.R = _DictGeomElem(self, 'R', self.__R)
        self.O = _DictGeomElem(self, 'O', self.__O)
        self.V = _DictGeomElem(self, 'V', self.__V)
        self.C = _DictGeomElem(self, 'C', self.__C)
        self.VOs = _DictGeomElem(self, 'VOs', self.__VOs)

        if upd_cl_us is None:
            self.update_cluster_usage = self._update_cluster_usage
        else:
            self.update_cluster_usage = types.MethodType(upd_cl_us, self)

        signal.signal(signal.SIGINT , lambda x, y: self.print_cluster_info())

    def load_header(self):
        self.mr = int(self.cfile.readline().split(':')[1].strip())
        self.m = int(self.cfile.readline().split(':')[1].strip())
        self.number_triangles = int(self.cfile.readline().split(':')[1].strip())

    def load_cluster(self, cl):
        init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
        self.cfile.seek(init_cluster)
        str_cluster = self.cfile.read(cluster_size)
    
        if len(self.cl_usage) == self.queue_size:
            #print "The queue is full"
            k = self.scd_policy(self.cl_usage)
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

        vertices = {}

        L = {}
        R = {}
        VOs = {}

        V = {}
        C = {}
        O = {}
        cluster = str_cluster.split('\n')
        for l in cluster:
            if l.startswith('v'):
                tmp = l.split()
                v_id = int(tmp[1])
                vertices[v_id] = [float(i) for i in tmp[2:]]
            elif l.startswith('L'):
                tmp = l.split()
                L[v_id] = [int(tmp[1]), int(tmp[2]), int(tmp[3])]
            elif l.startswith('R'):
                tmp = l.split()
                R[v_id] = [int(tmp[1]), int(tmp[2]), int(tmp[3])]
            elif l.startswith('S'):
                tmp = l.split()
                v_id = int(tmp[1])
                VOs[v_id] = [int(e) for e in tmp[2::]]

            elif l.startswith('V'):
                tmp = l.split()
                c_id = int(tmp[1])
                v_id = int(tmp[2])
                V[c_id] = v_id
            elif l.startswith('C'):
                tmp = l.split()
                v_id = int(tmp[1])
                c_id = int(tmp[2])
                C[v_id] = c_id
            elif l.startswith('O'):
                tmp = l.split()
                c_id = int(tmp[1])
                c_o = int(tmp[2])
                O[c_id] = c_o
        
        #try:
            #minv = min(vertices)
            #maxv = max(vertices)
        #except ValueError:
            #minv = min(V)
            #maxv = max(V)

        #if minv == maxv:
            #minv = min(V)
            #maxv = max(V)


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
            print cl
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
            #idx = bisect.bisect(self._clmrg.ic_keys, key)
            cl = self._clmrg.index_corners[str(key)]
            try:
                e = self._elems[cl][key]
                self._clmrg.hits += 1
            except KeyError:
                self._clmrg.load_cluster(cl)
                e = self._elems[cl][key]
        elif self._name == 'C':
            #idx = bisect.bisect(self._clmrg.icv_keys, key)
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
                idx = bisect.bisect(self._clmrg.iv_keys, key)
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
                    sys.exit()

        self._clmrg.update_cluster_usage(cl)
        return e

    def __setitem__(self, key, value):
        self._clmrg.access += 1
        try:
            if key >= self._clmrg.mr:
                cl = self._clmrg.index_isolated_vertices[str(key)]
            else:
                idx = bisect.bisect(self._clmrg.iv_keys, key)
                cl = self._clmrg.index_vertices[str(self._clmrg.iv_keys[idx] - 1)]
            self._elems[cl][key] = value
            self._clmrg.hits += 1
        except KeyError:
            self._clmrg.load_cluster(cl)
            self._elems[cl][key] = value

        self._clmrg.update_cluster_usage(cl)

    def __len__(self):
        return len(self._elems)


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
            print "S"
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

                cfile.write(" ".join([str(e) for e in elem]) + "\n")
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


def update_cluster_usage_lrfu(clmrg, cl_key):
    try:
        clmrg.cl_usage[cl_key]['crf'] = 1.0 + 2.0 ** (-clmrg.lbd) * clmrg.cl_usage[cl_key]['crf'] 
    except KeyError:
        clmrg.cl_usage[cl_key] = {'crf': 0}
        clmrg.cl_usage[cl_key]['crf'] = 1.0 + 2.0 ** (-clmrg.lbd) * clmrg.cl_usage[cl_key]['crf'] 

    for cl in clmrg.cl_usage:
        if cl != cl_key:
            clmrg.cl_usage[cl]['crf'] = 2 ** (-clmrg.lbd) * clmrg.cl_usage[cl]['crf']


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
                                       "lrfu"), default="lru")
    parser.add_argument('input')
    parser.add_argument('output')

    args = parser.parse_args()
    
    algorithms = {"lru": lru,
                  "lu": lu,
                  "mru": mru,
                  "mu": mu,
                  "random": randomized,
                  "lrfu": lrfu}

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
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)
        cl_lr = ClusteredLacedRing(clmrg)
        
        writer = ply_writer.PlyWriter(args.output)
        writer.from_laced_ring(cl_lr)

        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()

    elif args.r:
        if args.a == 'lrfu':
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], upd_cl_us=update_cluster_usage_lrfu)
        else:
            clmrg = ClusterManager(args.input, args.s, algorithms[args.a], args.l)

        cl_lr = ClusteredLacedRing(clmrg)

        random_access(cl_lr, int(args.output))

        if args.d:
            clmrg.print_cluster_info()

        if args.m:
            clmrg.print_hm_info()


if __name__ == '__main__':
    main()
