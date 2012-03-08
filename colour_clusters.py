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

def clusterize(faces, cluster_size):
    init_colour = 20
    end_colour = 256**3 - 1
    number_cluster = len(faces) / cluster_size
    if len(faces) % cluster_size:
        number_cluster += 1
    prop = (number_cluster / len(faces)) *  (end_colour - init_colour)
    colours = {}

    i = 0
    c = 0
    for f in faces:
        for v in f:
            colour = c * prop + init_colour
            r = round(colour % 256, 0)
            g = round((colour / 256) % 256, 0)
            b = round((colour / 256**2) % 256, 0)
            colours[v] = (r, g, b)

        i += 1
        if i % cluster_size == 0:
            c += 1

    print sorted(colours.values())[:100]
    return colours

def main():
    vertices, faces = read_ply(sys.argv[1])
    print sorted(vertices.keys())[:100]
    colours = clusterize(faces, float(sys.argv[3]))
    writer = ply_writer.PlyWriter(sys.argv[2])
    writer.from_faces_vertices_list(faces, vertices, colours)


if __name__ == '__main__':
    main()
