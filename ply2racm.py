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
            print v_id, line

            # Calculating the bounding box
            if bb_min is None:
                bb_min = vertex[v_id][:]
                bb_max = vertex[v_id][:]
            
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
    with file(racm_filename, 'w') as racm_file:
        pass

def main():
    import sys
    ply2racm(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
