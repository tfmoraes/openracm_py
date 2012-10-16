import bsddb
import os
import sys

import  bintrees
import numpy as np

import cy_corner_table
import laced_ring
import ply_reader

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
            print "Step", s, "vertex", i
            p = np.array(cllr.vertices[i])
            pl = p + l*D[i]
            nx, ny, nz = pl
            cllr.vertices[i] = nx, ny, nz


class ClusterManager(object):
    def __init__(self, filename, qsize):
        self.filename = filename
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_corner_vertices_file = os.path.splitext(filename)[0] + '_cv.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
        self.index_vertices = bsddb.btopen(index_vertices_file)
        self.index_corners_vertices = bsddb.btopen(index_corner_vertices_file)
        self.index_clusters = bsddb.btopen(index_clusters_file)

        self.cfile = open(filename)
        self.load_header()

        self.cl_usage = {}
        self.queue_size = qsize

        self._n_load_clusters = {}
        self._n_unload_clusters = {}

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

    def load_header(self):
        self.mr = int(self.cfile.readline().split(':')[1].strip())
        self.m = int(self.cfile.readline().split(':')[1].strip())
        self.number_triangles = int(self.cfile.readline().split(':')[1].strip())

    def load_cluster(self, cl):
        init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
        self.cfile.seek(init_cluster)
        str_cluster = self.cfile.read(cluster_size)

        if len(self.cl_usage) == self.queue_size:
            print "The queue is full"
            k = max(self.cl_usage, key=lambda x: x[1])[0]
            del self.cl_usage[k]
            del self.__vertices[k]
            del self.__L[k]
            del self.__R[k]
            del self.__VOs[k]
            del self.__O[k]
            del self.__V[k]
            del self.__C[k]

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
        
        try:
            minv = min(vertices)
            maxv = max(vertices)
        except ValueError:
            minv = min(V)
            maxv = max(V)

        self.__vertices[(minv, maxv)] = vertices
        self.__L[(minv, maxv)] = L
        self.__R[(minv, maxv)] = R
        self.__VOs[(minv, maxv)] = VOs
        self.__V[(minv, maxv)] = V
        self.__C[(minv, maxv)] = C
        self.__O[(minv, maxv)] = O

        if minv == 0:
            print self.__V

        try:
            self._n_load_clusters[(minv, maxv)] += 1
        except KeyError:
            self._n_load_clusters[(minv, maxv)] = 1
            self._n_unload_clusters[(minv, maxv)] = 0

    def load_vertex_cluster(self, v_id):
        print ">>>", v_id
        cl = self.index_vertices[str(v_id)]
        print "Loading Cluster", cl
        return self.load_cluster(cl)

    def load_corner_cluster(self, c_id):
        print ">>>", c_id
        cl = self.index_corners_vertices[str(c_id)]
        print "Loading Cluster", cl
        return self.load_cluster(cl)

    def print_cluster_info(self):
        for k in sorted(self._n_load_clusters):
            print k, self._n_load_clusters[k], self._n_unload_clusters[k]

        print self.cl_usage


    def update_cluster_usage(self, cl_key):
        try:
            self.cl_usage[cl_key] += 1
        except KeyError:
            self.cl_usage[cl_key] = 1


class _DictGeomElem(object):
    def __init__(self, clmrg, name, elems):
        self._elems = elems
        self._name = name
        self._clmrg = clmrg

    def __getitem__(self, key):
        for minv, maxv in sorted(self._elems):
            if minv <= key <= maxv:
                break
        else:
            if self._name in ('V', 'O'):
                self._clmrg.load_corner_cluster(key)
            else:
                self._clmrg.load_vertex_cluster(key)
            for minv, maxv in sorted(self._elems):
                if minv <= key <= maxv:
                    break
            else:
                return
        #if minv == 0:
            #print self._elems[(minv, maxv)]
        self._clmrg.update_cluster_usage((minv, maxv))
        return self._elems[(minv, maxv)][key]

    def __setitem__(self, key, value):
        for minv, maxv in sorted(self._elems):
            if minv <= key <= maxv:
                break

        self._elems[(minv, maxv)][key] = value
        self._clmrg.update_cluster_usage((minv, maxv))

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
    for t in xrange(0, lr.mr):
        if t % cluster_size == 0:
            n += 1
            clusters.append([])

        clusters[n].append(('v', v_id, lr.vertices[v_id][0], lr.vertices[v_id][1], lr.vertices[v_id][2]))
        clusters[n].append(('L', lr.L[v_id][0], lr.L[v_id][1], lr.L[v_id][2]))
        clusters[n].append(('R', lr.R[v_id][0], lr.R[v_id][1], lr.R[v_id][2]))

        if lr.L[v_id][2] or lr.R[v_id][2]:
            print "S"
            clusters[n].append(('S', v_id, lr.VOs[v_id][0], lr.VOs[v_id][1], lr.VOs[v_id][2], lr.VOs[v_id][3])) 

        v_id += 1

    n += 1
    clusters.append([])
    for v_id in xrange(lr.mr, lr.m):
        clusters[n].append(('v', v_id, lr.vertices[v_id][0], lr.vertices[v_id][1], lr.vertices[v_id][2]))

    print lr.mr, lr.m, lr.number_triangles, len(lr.vertices)
    for t in xrange(lr.mr * 2, lr.number_triangles):
        c0 = lr.corner_triangle(t)
        c1 = lr.next_corner(c0)
        c2 = lr.previous_corner(c0)
        clusters[n].append(('V', c0, lr.vertex(c0)))
        clusters[n].append(('C', lr.vertex(c0), c0))
        clusters[n].append(('O', c0, lr.oposite(c0)[0]))

        clusters[n].append(('V', c1, lr.vertex(c1)))
        clusters[n].append(('C', lr.vertex(c1), c1))
        clusters[n].append(('O', c1, lr.oposite(c1)[0]))

        clusters[n].append(('V', c2, lr.vertex(c2)))
        clusters[n].append(('C', lr.vertex(c2), c2))
        clusters[n].append(('O', c2, lr.oposite(c2)[0]))

    return clusters

def save_clusters(lr, clusters, filename):
    with file(filename, 'w') as cfile:
        # indexes
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_corner_vertices_file = os.path.splitext(filename)[0] + '_cv.hdr'
        index_vertices = bsddb.btopen(index_vertices_file)
        index_corners_vertices = bsddb.btopen(index_corner_vertices_file)
        index_clusters = bsddb.btopen(index_clusters_file)

        cfile.write("edge vertex: %d\n" % lr.mr)
        cfile.write("vertex: %d\n" % lr.m)
        cfile.write("triangles: %d\n" % lr.number_triangles)

        for i, cluster in enumerate(clusters):
            #cfile.write("Cluster %d\n" % i)
            init_cluster = cfile.tell()
            minc, maxc = 2**32, 0
            for elem in cluster:
                if elem[0] == 'v':
                    maxc = max(elem[1], maxc)
                    minc = min(elem[1], minc)
                    index_vertices[str(elem[1])] = str(i)
                elif elem[0] == 'V':
                    index_corners_vertices[str(elem[1])] = str(i)

                cfile.write(" ".join([str(e) for e in elem]) + "\n")
            cluster_size = cfile.tell() - init_cluster
            index_clusters[str(i)] = "%d %d %d %d" % (init_cluster,
                                                             cluster_size,
                                                             minc,
                                                             maxc)
       

def main():
    if sys.argv[1] == '-c':
        vertices, faces = laced_ring.read_ply(sys.argv[2])
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
        clusters = create_clusters(lr, int(sys.argv[3]))
        save_clusters(lr, clusters, sys.argv[4])

    elif sys.argv[1] == '-o':
        clmrg = ClusterManager(sys.argv[2], int(sys.argv[3]))
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

        taubin_smooth(cl_lr, 0.5, -0.53, 3)


        if "-d" in sys.argv:
            clmrg.print_cluster_info()


if __name__ == '__main__':
    main()
