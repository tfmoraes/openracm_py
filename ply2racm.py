#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import argparse
import cy_corner_table
import cy_sorter
import ply_reader
import ply_writer
import sorter
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


def ply2racm(ply_filename, racm_filename, buffer_size, algorithm, cluster_size=200):
    vertices = {}
    faces = {}
    vertices_faces = {}
    vertices_face_count = []
    bb_min = None
    bb_max = None
    v_id = 0
    f_id = 0
    reader = ply_reader.PlyReader(ply_filename)
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            current_vertex = data
            vertices[v_id] = current_vertex
            vertices_face_count.append(0)

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
                try:
                    vertices_faces[v].append(f_id)
                except KeyError:
                    vertices_faces[v] = [f_id,]
                vertices_face_count[v] += 1
            f_id += 1

    print bb_min, bb_max

    if algorithm == 'tipsify':
        foutput = sorter.tipsify(faces, buffer_size, vertices_faces, vertices_face_count)
    else:
        ct = cy_corner_table.CornerTable()
        ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)
        foutput = cy_sorter.k_cache_reorder(ct, buffer_size)
        foutput = [faces[i] for i in foutput]

    if racm_filename.endswith('.ply'):
        writer = ply_writer.PlyWriter(racm_filename)
        writer.from_faces_vertices_list(foutput, vertices)
    elif racm_filename.endswith('.wrl'):
        writer = wrl_writer.WrlWriter(racm_filename)
        writer.from_faces_vertices_list(foutput, vertices)

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
    parser = argparse.ArgumentParser(description="Ply to openracm")
    parser.add_argument('input', help='A Ply input file')
    parser.add_argument('output', help='A Ply or a WRL output file')
    parser.add_argument('-b', dest="buffer_size", type=int, default=12)
    parser.add_argument('-a', dest='algorithm', choices=('tipsify', 'k-cache-reorder'),
                        default='tipsify', help="The algorithm used to sort the"\
                        "mesh Tipsify or k-cache-reorder")
    args = parser.parse_args()

    ply2racm(args.input, args.output, args.buffer_size, args.algorithm)

if __name__ == '__main__':
    main()
