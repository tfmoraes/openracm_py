import bsddb
import os
import sys

class Cluster2STL(object):
    def __init__(self, filename, stl_filename):
        self.filename = filename
        self.stl_filename = stl_filename
        index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
        index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
        self.index_vertices = bsddb.btopen(index_vertices_file)
        self.index_clusters = bsddb.btopen(index_clusters_file)
        self.loaded_clusters = []
        self.faces = {}
        self.vertices = {}
        self._make_clusters_maps()

    def _make_clusters_maps(self):
        self.map_clusters = {}
        for i in self.index_clusters:
            init_cluster, cluster_size, iface, eface = self.index_clusters[i].split()
            self.map_clusters[int(i)] = {'init_cluster': int(init_cluster),
                                         'cluster_size': int(cluster_size),
                                         'init_face': int(iface),
                                         'last_face': int(eface),
                                        }


    def from_cluster_to_stl(self):
        with file(self.filename, 'r') as self.cfile:
            nclusters = int(self.cfile.readline().split()[-1])
            nvertices = int(self.cfile.readline().split()[-1])
            nfaces = int(self.cfile.readline().split()[-1])

            print nclusters, nvertices, nfaces

            with file(self.stl_filename, 'w') as self.sfile:
                self.sfile.write('solid vcg\n')
                for face in xrange(nfaces):
                    if face not in self.faces:
                        ncluster = self._find_face(face)
                        self._load_cluster(ncluster)
                        print ncluster, face

                    self.sfile.write('\tface normal  5.017158e-02  8.838527e-01 4.650667e-01\n')
                    self.sfile.write('\t\touter loop\n')

                    for v in self.faces[face]:
                        if abs(v) not in self.vertices:
                            ncluster = int(self.index_vertices[str(abs(v))])
                            self._load_cluster(ncluster)

                        self.sfile.write('\t\t\tvertex %f %f %f\n' % self.vertices[abs(v)])

                        if v < 0:
                            del self.vertices[abs(v)]

                    self.sfile.write('\t\tendloop\n')
                    self.sfile.write('\tendfacet\n')

                    del self.faces[face]

                self.sfile.write('endsolid vcg')

    def _find_face(self, face):
        for i in self.map_clusters:
            init_face = self.map_clusters[i]['init_face']
            end_face = self.map_clusters[i]['last_face']

            if init_face <= face <= end_face:
                return i

    def _load_cluster(self, ncluster):
        if ncluster not in self.loaded_clusters:
            self.loaded_clusters.append(ncluster)
            init_cluster = self.map_clusters[ncluster]['init_cluster']
            cluster_size = self.map_clusters[ncluster]['cluster_size']

            self.cfile.seek(init_cluster)
            str_cluster = self.cfile.read(cluster_size)

            for l in str_cluster.split('\n'):
                if l.startswith('v'):
                    v, x, y, z = l.split()[1:]
                    self.vertices[int(v)] = float(x), float(y), float(z)
                elif l.startswith('f'):
                    f, v0, v1, v2 = l.split()[1:]
                    self.faces[int(f)] = (int(v0), int(v1), int(v2))
                else:
                    # TODO: Raise a exception
                    pass


def main():
    c2p = Cluster2STL(sys.argv[1], sys.argv[2])
    c2p.from_cluster_to_stl()

if __name__ == '__main__':
    main()
