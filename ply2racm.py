#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import cy_corner_table
import ply_reader
import ply_writer
import cy_sorter
import wrl_writer

def calculate_d(ct, c_id):
    t = [0.0, 0.0, 0.0]
    n = 0.0
    visited = {}
    v = ct.get_vertex(c_id)
    cc_id = c_id
    while 1:
        cn = ct.next_corner(cc_id)
        cp = ct.previous_corner(cc_id)

        vn = ct.get_vertex(cn)
        vp = ct.get_vertex(cp)

        if not visited.get(ct.V[cn], 0):
            visited[ct.V[cn]] = 1
            t = (t[0] + (vn[0] - v[0]), t[1] + (vn[1] - v[1]), t[2] + (vn[2] - v[2]))
            n += 1

        if not visited.get(ct.V[cp], 0):
            visited[ct.V[cp]] = 1
            t = (t[0] + (vp[0] - v[0]), t[1] + (vp[1] - v[1]), t[2] + (vp[2] - v[2]))
            n += 1

        cc_id = ct.swing(cc_id)
        if ct.get_triangle(c_id) == ct.get_triangle(cc_id):
            break

    return [i/n for i in t]

def taubin_smooth(ct, l, m, steps):
    for s in xrange(steps):
        visited = {}
        D = {}
        for c_id in xrange(len(ct.V)):
            v = ct.V[c_id]
            if not visited.get(v, 0):
                D[v] = calculate_d(ct, c_id)
                visited[v] = 1
        for v in D:
            vp = ct.vertices[v]
            d = D[v]
            ct.vertices[v] = [x + l*y for x,y in zip(vp, d)]

        visited = {}
        D = {}
        for c_id in xrange(len(ct.V)):
            v = ct.V[c_id]
            if not visited.get(v, 0):
                D[v] = calculate_d(ct, c_id)
                visited[v] = 1
        for v in D:
            vp = ct.vertices[v]
            d = D[v]
            ct.vertices[v] = [x + m*y for x,y in zip(vp, d)]


def ply2racm(ply_filename, racm_filename, cluster_size=200):
    vertices = {}
    faces = {}
    vertices_faces = {}
    bb_min = None
    bb_max = None
    v_id = 0
    f_id = 0
    reader = ply_reader.PlyReader(ply_filename)
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices[v_id] = current_vertex[:] + [0,]

            # Calculating the bounding box
            if v_id == 0:
                bb_min = current_vertex
                bb_max = current_vertex
            else:
                bb_min = [min(cv, bm) for cv,bm in zip(current_vertex, bb_min)]
                bb_max = [max(cv, bm) for cv,bm in zip(current_vertex, bb_max)]
            v_id += 1

        elif evt == ply_reader.EVENT_FACE:
            faces[f_id] = data
            for v in faces[f_id]:
                vertices[v][-1] += 1
                try:
                    vertices_faces[v].append(f_id)
                except KeyError:
                    vertices_faces[v] = [f_id,]
            f_id += 1

    print bb_min, bb_max

    ct = cy_corner_table.CornerTable()
    ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)

    foutput = cy_sorter.k_cache_reorder(ct)

    print len(faces.keys())
    print 
    print len(foutput)

    #taubin_smooth(ct, 0.5, -0.53, 10)

    #writing a output ply from taubin smooth algorithm
    writer = wrl_writer.WrlWriter(racm_filename)
    writer.from_faces_vertices_list([faces[i] for i in foutput], vertices)
    #writer.from_corner_table(ct)

    #print [ct.V[i] for i in ct.O]
    #print 
    #print [(n, get_triangle(V, n), V[i]) for n, i in enumerate(O)]

    # Writing to racm file
    #working_vertex = []
    #last_vertex = -1
    #with file(racm_filename, 'w') as racm_file:
        #racm_file.write('header\n')
        #racm_file.write('vertex %d\n' % n_vertex)
        #racm_file.write('faces %d\n' % n_faces)
        #racm_file.write('bb_min: %s\n' % ','.join([str(i) for i in bb_min]))
        #racm_file.write('bb_max: %s\n' % ','.join([str(i) for i in bb_max]))
        #racm_file.write('end header\n')

        #for face in sorted(faces):
            #face_vertices = faces[face]
            #max_vertex = max(face_vertices)
            #if last_vertex < max_vertex:
                #for v in xrange(last_vertex+1, max_vertex+1):
                    #racm_file.write('v %s\n' % ','.join([str(i) for i in vertices[v][:3]]))
                    #working_vertex.append(v)
                #last_vertex = max_vertex

            #for v in face_vertices:
                #vertices[v][3] -= 1

            #racm_file.write('f %s\n' % ','.join([str(i) if vertices[i][3] > 0
                                                 #else '-%d' % i for i in face_vertices]))



def main():
    import sys
    ply2racm(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
