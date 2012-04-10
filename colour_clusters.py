import argparse
import bsddb
import os
import sys

import ply_reader
import ply_writer

def read_ply(ply_filename):
    vertices = {}
    faces = []
    reader = ply_reader.PlyReader(ply_filename)
    v_id = 0
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices[v_id] = current_vertex
            v_id += 1

        elif evt == ply_reader.EVENT_FACE:
            faces.append(data)

    return vertices, faces

def colorize_clusters(faces, clusters):
    init_colour = 20
    end_colour = 256**3 - 1
    number_cluster = len(clusters)
    prop = (number_cluster / float(len(faces))) *  (end_colour - init_colour)
    colours = {}

    for nc, c in enumerate(clusters):
        for f in c:
            for v in faces[f]:
                colour = nc * prop + init_colour
                r = round(colour % 256, 0)
                g = round((colour / 256) % 256, 0)
                b = round((colour / 256**2) % 256, 0)
                colours[v] = (r, g, b)

    print sorted(colours.values())[:100]
    return colours

def clusterize(faces, cluster_size):
    cluster_verices = set()
    cluster = []
    n_faces = 0
    for n, f in enumerate(faces):
        flag_cluster = 0
        for v in f:
            if v not in cluster_verices:
                cluster_verices.add(v)
                flag_cluster += 1
        if (flag_cluster == 3) or n_faces == cluster_size:
            n_faces = 1
            cluster.append([n, ])
            cluster_verices = set(f)
        else:
            n_faces += 1
            cluster[-1].append(n)
    for i in cluster:
        print i

    return cluster

    


def save_clusters(clusters, vertices, faces, filename):
    counts = {}
    for f in faces:
        for v in f:
            try:
                counts[v] += 1
            except KeyError:
                counts[v] = 1

    index_vertices_file = os.path.splitext(filename)[0] + '_v.hdr'
    index_clusters_file = os.path.splitext(filename)[0] + '_c.hdr'
    index_vertices = bsddb.btopen(index_vertices_file)
    index_clusters = bsddb.btopen(index_clusters_file)
    
    with file(filename, 'w') as cfile:
        working_vertex = {}
        cfile.write('Number of cluster: %d\n' % len(clusters))
        cfile.write('Number of vertices: %d\n' % len(vertices))
        cfile.write('Number of faces: %d\n' % len(faces))
        for ncluster, cluster in enumerate(sorted(clusters)):
            init_cluster = cfile.tell()
            for f in sorted(cluster):
                for v in faces[f]:
                    if v not in working_vertex:
                        cfile.write('v %d ' % v)
                        cfile.write('%f %f %f\n' % tuple(vertices[v]))
                        working_vertex[v] = True
                        index_vertices[str(v)] = str(ncluster)
                
                fline = []
                for v in faces[f]:
                    counts[v] -= 1
                    if counts[v] == 0:
                        fline.append(-v)
                        del working_vertex[v]
                    else:
                        fline.append(v)
                cfile.write('f %d ' % f)
                cfile.write('%d %d %d\n' % tuple(fline))

            cluster_size = cfile.tell() - init_cluster
            index_clusters[str(ncluster)] = "%d %d %d %d" % (init_cluster,
                                                             cluster_size,
                                                             sorted(cluster)[0],
                                                             sorted(cluster)[-1])


def main():
    parser = argparse.ArgumentParser(description="Clusterize a mesh.")
    parser.add_argument('input', help='A Ply input file')
    parser.add_argument('output', help='A Ply output file')
    parser.add_argument('-c', dest="cluster_size", type=int, default=1000,
                        help="The size of each cluster")
    parser.add_argument('-x', action='store_true', help="Each cluster is saved in different file")
    args = parser.parse_args()

    vertices, faces = read_ply(args.input)
    clusters = clusterize(faces, args.cluster_size)
    colours = colorize_clusters(faces, clusters) 

    if args.x:
        number_cluster = len(faces) / float(args.cluster_size)
        if len(faces) % args.cluster_size:
            number_cluster += 1
        
        basename, extension = os.path.splitext(args.output)
        for n, cfaces in enumerate(clusters):
            writer = ply_writer.PlyWriter('%s_%d%s' % (basename, n, extension))
            writer.from_faces_vertices_list([faces[f] for f in cfaces], vertices, colours)
    else:
        #writer = ply_writer.PlyWriter(args.output)
        #writer.from_faces_vertices_list(faces, vertices, colours)
        save_clusters(clusters, vertices, faces, args.output)


if __name__ == '__main__':
    main()
