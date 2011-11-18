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
        vertex = {}
        v_id = 0
        bb_min = None
        bb_max = None
        for line in ply_file:
            vertex[v_id] = [float(v) for v in line.split()] + [0,]

            # Calculating the bounding box
            if bb_min is None:
                bb_min = vertex[v_id][:3]
                bb_max = vertex[v_id][:3]
            
            if bb_min[0] > vertex[v_id][0]:
                bb_min[0] = vertex[v_id][0]

            if bb_min[1] > vertex[v_id][1]:
                bb_min[1] = vertex[v_id][1]

            if bb_min[2] > vertex[v_id][2]:
                bb_min[2] = vertex[v_id][2]

            if bb_max[0] < vertex[v_id][0]:
                bb_max[0] = vertex[v_id][0]

            if bb_max[1] < vertex[v_id][1]:
                bb_max[1] = vertex[v_id][1]

            if bb_max[2] < vertex[v_id][2]:
                bb_max[2] = vertex[v_id][2]

            v_id += 1
            if v_id == n_vertex:
                break

        # reading faces
        faces = {}
        f_id = 0
        for line in ply_file:
            faces[f_id] = [int(v) for v in line.split()][1:4]
            for v in faces[f_id]:
                vertex[v][-1] += 1
            f_id += 1
            if f_id == n_faces:
                break

    print n_faces, n_vertex, bb_min, bb_max
    # Writing to racm file
    working_vertex = []
    last_vertex = 0
    with file(racm_filename, 'w') as racm_file:
        racm_file.write('header\n')
        racm_file.write('vertex %d\n' % n_vertex)
        racm_file.write('faces %d\n' % n_faces)
        racm_file.write('bb_min: %s\n' % ','.join([str(i) for i in bb_min]))
        racm_file.write('bb_max: %s\n' % ','.join([str(i) for i in bb_max]))
        racm_file.write('end header\n')

        for face in sorted(faces):
            vertices = faces[face]
            if last_vertex != max(vertices):
                for v in xrange(last_vertex, max(vertices)+1):
                    racm_file.write('v %s\n' % ','.join([str(i) for i in vertex[v][:3]]))
                    working_vertex.append(v)
                last_vertex = max(vertices)

            for v in vertices:
                vertex[v][3] -= 1

            racm_file.write('f %s\n' % ','.join([str(i if vertex[i][3] > 0 else -i) for i in vertices]))



def main():
    import sys
    ply2racm(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
