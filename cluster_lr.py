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

    def load_cluster(self, cl):
        init_cluster, cluster_size, iface, eface = [int(i) for i in self.index_clusters[cl].split()]
        self.cfile.seek(init_cluster)
        str_cluster = self.cfile.read(cluster_size)
        return str_cluster.split('\n')

    def load_vertex_cluster(self, v_id):
        cl = self.index_vertices[str(v_id)]
        return self.load_cluster(cl)


class _DictGeomElem(object):
    def __init__(self, clmrg):
        self._elems = {}
        self._clmrg = clmrg

    def __getitem__(self, key):
        if key not in self._elems:
            cluster = self._clmrg.load_vertex_cluster(key)

            for l in cluster:
                if l.startswith('v'):
                    tmp = l.split()
                    self._elems[int(tmp[1])] = [float(i) for i in tmp[2:]]

        return self._elems[key]

class ClusteredLacedRing(laced_ring.LacedRing):
    def __init__(self, clmrg):
        self.cluster_manager = clmrg
        self.vertices = _DictGeomElem(self.cluster_manager)
        #self.faces = faces
        #self.edge_ring = edge_ring
        #self.m_t = m_t
        self.L = _DictGeomElem(self.cluster_manager)
        self.R = _DictGeomElem(self.cluster_manager)
        self.O = _DictGeomElem(self.cluster_manager)
        self.V = _DictGeomElem(self.cluster_manager)
        self.C = _DictGeomElem(self.cluster_manager)
        self.VOs = _DictGeomElem(self.cluster_manager)
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
        print cl_lr.get_vertex_coord(int(sys.argv[3]))


if __name__ == '__main__':
    main()
