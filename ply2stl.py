import os
import ply_reader

def read_ply(ply_filename):
    reader = ply_reader.PlyReader(ply_filename)
    vertices = []
    faces = []
    # Reading the header
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_HEADER:
            n_vertices, n_faces = data
            break

    # Reading the vertices and faces
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices.append(current_vertex)

        elif evt == ply_reader.EVENT_FACE:
            faces.append(data)

    return vertices, faces

def ply2stl(ply_filename, stl_filename):
    vertices, faces = read_ply(ply_filename)
    with file(stl_filename, 'w') as stl_file:
        stl_file.write('solid vcg\n')
        for face in faces:
            stl_file.write('\tface normal  5.017158e-02  8.838527e-01 4.650667e-01\n')
            stl_file.write('\t\touter loop\n')
            
            for vertex in face:
                print vertex, vertices[vertex]
                stl_file.write('\t\t\tvertex %f %f %f\n' % tuple(vertices[vertex]))

            stl_file.write('\t\tendloop\n')
            stl_file.write('\tendfacet\n')

        stl_file.write('endsolid vcg')

def main():
    import sys
    ply2stl(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
