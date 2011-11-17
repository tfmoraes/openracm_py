def ply2racm(ply_filename, racm_filename):
    with open(ply_filename, 'r') as ply_file:
        for line in ply_file:
            # reading header
            if line.startswith('element vertex'):
                n_vertex = int(line.split()[2])
            elif line.startswith('element face'):
                n_faces = int(line.split()[2])
            elif line.startswith('end_header'):
                break

        print n_faces, n_vertex
        # reading vertex
        vertex = {}
        v_id = 0
        for line in ply_file:
            vertex[v_id] = [float(v) for v in line.split()]
            v_id += 1
            if v_id == n_vertex:
                break

        # reading faces
        faces = {}
        f_id = 0
        for line in ply_file:
            faces[f_id] = [int(v) for v in line.split()][1:4]
            f_id += 1
            if f_id == n_faces:
                break




    #racm_file = open(racm_filename, 'w')

def main():
    import sys
    ply2racm(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
