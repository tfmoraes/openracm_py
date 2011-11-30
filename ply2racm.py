def get_triangle(V, v_id):
    return v_id / 3

def get_corner(f_id):
    return f_id * 3

def next_corner(V, v_id):
    return 3 * get_triangle(V, v_id) + ((v_id + 1) % 3)

def previous_corner(V, v_id):
    return next_corner(V, next_corner(V, v_id))

def iterate_triangle_corner(V, f_id):
    corner = get_corner(f_id)
    yield corner
    yield next_corner(V, corner)
    yield previous_corner(V, corner)

def computeO(V, vertices, faces, vertices_faces):
    O = []
    for i in xrange(len(V)):
        O.append(-1)
    for v_id in xrange(len(V)):
        t = get_triangle(V, v_id)
        c0 = next_corner(V, v_id)
        c1 = previous_corner(V, v_id)
        v0 = V[c0]
        v1 = V[c1]
        f = set(vertices_faces[v0]) & set(vertices_faces[v1])
        if len(f) != 2:
            raise("Error")
        f0, f1 = f
        if t == f0:
            oface = f1
        elif t == f1:
            oface = f0
        else:
            raise("Error")

        for n,c in enumerate(iterate_triangle_corner(V, oface)):
            if V[c] not in (V[c0], V[c1]):
                O[v_id] = c
                print t, V[v_id], oface, V[c]
                break

        #for vertex in oface:
            #if not vertex in (v0, v1):
                #O[v_id] = vertex
                #break

        
    return O


def computeV(vertices, faces, vertices_faces):
    V = []
    v_id = 0
    for face in sorted(faces):
        for vertex in faces[face]:
            V.append(vertex)
    return V


def ply2racm(ply_filename, racm_filename, cluster_size=200):
    with open(ply_filename, 'r') as ply_file:
        for line in ply_file:
            # reading header
            if line.startswith('element vertex'):
                n_vertex = int(line.split()[2])
            elif line.startswith('element face'):
                n_faces = int(line.split()[2])
            elif line.startswith('end_header'):
                break

        # reading vertex
        vertices = {}
        v_id = 0
        bb_min = None
        bb_max = None
        for line in ply_file:
            current_vertex = [float(v.replace(',', '.')) for v in line.split()][:3]
            vertices[v_id] = current_vertex[:] + [0,]

            # Calculating the bounding box
            if v_id == 0:
                bb_min = current_vertex
                bb_max = current_vertex
            else:
                bb_min = [min(cv, bm) for cv,bm in zip(current_vertex, bb_min)]
                bb_max = [max(cv, bm) for cv,bm in zip(current_vertex, bb_max)]
            
            v_id += 1
            if v_id == n_vertex:
                break

        # reading faces
        faces = {}
        vertices_faces = {}
        f_id = 0
        for line in ply_file:
            faces[f_id] = [int(v) for v in line.split()][1:4]
            for v in faces[f_id]:
                vertices[v][-1] += 1
                try:
                    vertices_faces[v].append(f_id)
                except KeyError:
                    vertices_faces[v] = [f_id,]
            f_id += 1
            if f_id == n_faces:
                break

    print n_faces, n_vertex, bb_min, bb_max

    V = computeV(vertices, faces, vertices_faces)
    O = computeO(V, vertices, faces, vertices_faces)

    print [V[i] for i in O]
    print 
    print [(n, get_triangle(V, n), V[i]) for n, i in enumerate(O)]

    # Writing to racm file
    working_vertex = []
    last_vertex = -1
    with file(racm_filename, 'w') as racm_file:
        racm_file.write('header\n')
        racm_file.write('vertex %d\n' % n_vertex)
        racm_file.write('faces %d\n' % n_faces)
        racm_file.write('bb_min: %s\n' % ','.join([str(i) for i in bb_min]))
        racm_file.write('bb_max: %s\n' % ','.join([str(i) for i in bb_max]))
        racm_file.write('end header\n')

        for face in sorted(faces):
            face_vertices = faces[face]
            max_vertex = max(face_vertices)
            if last_vertex < max_vertex:
                for v in xrange(last_vertex+1, max_vertex+1):
                    racm_file.write('v %s\n' % ','.join([str(i) for i in vertices[v][:3]]))
                    working_vertex.append(v)
                last_vertex = max_vertex

            for v in face_vertices:
                vertices[v][3] -= 1

            racm_file.write('f %s\n' % ','.join([str(i) if vertices[i][3] > 0
                                                 else '-%d' % i for i in face_vertices]))



def main():
    import sys
    ply2racm(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
