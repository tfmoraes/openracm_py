import bsddb
import os
import sys

import cy_corner_table
import laced_ring
import ply_reader

class ClusterManager(object):
    def __init__(self, filename):
        self.filename = filename
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
        self.index_vertices = bsddb.btopen(index_vertices_file)
        self.index_clusters = bsddb.btopen(index_clusters_file)

        self.cfile = open(filename)
        self.mr = int(self.cfile.readline().strip())

        self.__vertices = {}
        self.__L = {}
        self.__R = {}
        self.__O = {}
        self.__V = {}
        self.__C = {}
        self.__VOs = {}

        self.vertices = _DictGeomElem(self, self.__vertices)
        self.L = _DictGeomElem(self, self.__L)
        self.R = _DictGeomElem(self, self.__R)
        self.O = _DictGeomElem(self, self.__O)
        self.V = _DictGeomElem(self, self.__V)
        self.C = _DictGeomElem(self, self.__C)
        self.VOs = _DictGeomElem(self, self.__VOs)

    def load_cluster(self, cl):
        init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
        self.cfile.seek(init_cluster)
        str_cluster = self.cfile.read(cluster_size)
        
        V = {}
        L = {}
        R = {}
        cluster = str_cluster.split('\n')
        for l in cluster:
            if l.startswith('v'):
                tmp = l.split()
                v_id = int(tmp[1])
                V[v_id] = [float(i) for i in tmp[2:]]
            elif l.startswith('L'):
                tmp = l.split()
                L[v_id] = [int(tmp[1]), 0, 0]
            elif l.startswith('R'):
                tmp = l.split()
                R[v_id] = [int(tmp[1]), 0, 0]
        
        minv = min(V)
        maxv = max(V)
        self.__vertices[(minv, maxv)] = V
        self.__L[(minv, maxv)] = L
        self.__R[(minv, maxv)] = R
        

    def load_vertex_cluster(self, v_id):
        cl = self.index_vertices[str(v_id)]
        print "Loading Cluster", cl
        return self.load_cluster(cl)


class _DictGeomElem(object):
    def __init__(self, clmrg, elems):
        self._elems = elems
        self._clmrg = clmrg

    def __getitem__(self, key):
        for minv, maxv in sorted(self._elems):
            if minv <= key <= maxv:
                break
        else:
            self._clmrg.load_vertex_cluster(key)
            for minv, maxv in sorted(self._elems):
                if minv <= key <= maxv:
                    break
        return self._elems[(minv, maxv)][key]

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
        self.number_triangles = 0

        self.mr = self.cluster_manager.mr

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
        clusters[n].append(('L', lr.L[v_id][0]))
        clusters[n].append(('R', lr.R[v_id][0]))

        v_id += 1

    return clusters

def save_clusters(lr, clusters, filename):
    with file(filename, 'w') as cfile:
        # indexes
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
        index_vertices = bsddb.btopen(index_vertices_file)
        index_clusters = bsddb.btopen(index_clusters_file)

        cfile.write("%d\n" % lr.mr)

        for i, cluster in enumerate(clusters):
            #cfile.write("Cluster %d\n" % i)
            init_cluster = cfile.tell()
            for elem in cluster:
                if elem[0] == 'v':
                    index_vertices[str(elem[1])] = str(i)
                cfile.write(" ".join([str(e) for e in elem]) + "\n")
            cluster_size = cfile.tell() - init_cluster
            index_clusters[str(i)] = "%d %d %d %d" % (init_cluster,
                                                             cluster_size,
                                                             sorted(cluster)[0][1],
                                                             sorted(cluster)[-1][1])
       

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
        clmrg = ClusterManager(sys.argv[2])
        cl_lr = ClusteredLacedRing(clmrg)
        #cl_lr.to_vertices_faces()

        for i in xrange(cl_lr.mr):
            print i, cl_lr.get_vertex_coord(i)
            print cl_lr.L[i], cl_lr.get_vertex_coord(cl_lr.L[i][0])
            print cl_lr.R[i], cl_lr.get_vertex_coord(cl_lr.R[i][0])


if __name__ == '__main__':
    main()
