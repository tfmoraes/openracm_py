import sys

import cy_corner_table
import laced_ring
import ply_reader

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

def save_clusters(clusters, filename):
    with file(filename, 'w') as cfile:
        for i, cluster in enumerate(clusters):
            cfile.write("Cluster %d\n" % i)
            for elem in cluster:
                cfile.write(" ".join([str(e) for e in elem]) + "\n")

       

def main():
    vertices, faces = laced_ring.read_ply(sys.argv[1])
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
    clusters = create_clusters(lr, int(sys.argv[2]))
    save_clusters(clusters, sys.argv[3])


if __name__ == '__main__':
    main()
