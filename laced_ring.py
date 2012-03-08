#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import random
import sys
import ply_reader
import cy_corner_table
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


def ring_expander(ct):
    s = 0 #random.randint(0, len(ct.V))
    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}

    while 1:
        print c, ct.get_oposite_corner(s)
        if not m_v.get(ct.get_vertex(c), 0):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1
        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)
        c = ct.get_right_corner(c)

        if c == ct.get_oposite_corner(s):
            break

    return m_v


def clusterize_ct(ct, cluster_size):
    number_cluster = (len(ct.V)/3) / cluster_size
    if (len(ct.V)/3) % cluster_size:
        number_cluster += 1

    clusters = {}
    for n in xrange(number_cluster):
        clusters[n] = range(n * cluster_size,
                            (n + 1) * cluster_size)
    return clusters
    

def make_vertex_faces(vertices, faces):
    vertices_faces = {}
    for f_id, face in enumerate(faces):
        for v in face:
            try:
                vertices_faces[v].append(f_id)
            except KeyError:
                vertices_faces[v] = [f_id,]
    return vertices_faces

def expand_ring_into_cluster(ct, ncluster, clusters):
    #s = ct.get_corner_f(random.randint(min(clusters[ncluster]),
                                       #max(clusters[ncluster])))
    min_, max_ = min(clusters[ncluster]), max(clusters[ncluster])
    s = ct.get_corner_f(min_)


    c = s
    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}

    while 1:
        if not m_v.get(ct.get_vertex(c), 0):
            if min_ <= ct.get_triangle(c) < max_:
                m_v[ct.get_vertex(c)] = 1
                m_t[ct.get_triangle(c)] = 1
            else:
                c = ct.get_oposite_corner(c)
        elif not m_t.get(ct.get_triangle(c), 0):
            c = ct.get_oposite_corner(c)

        #elif (not min_ <= ct.get_triangle(c) < max_) and (not m_t.get(ct.get_triangle(c), 0)) :
            ##print n, ct.get_triangle(c), min_, max_
            #c = ct.get_oposite_corner(c)
            ##c = ct.get_right_corner(c)
            ##print n, ct.get_triangle(c), min_, max_
        c = ct.get_right_corner(c)
        if c == ct.get_oposite_corner(s):
            break

    print len(m_v), len(m_t)

    return m_v

def hybrid_expand_ring_into_cluster(ct, ncluster, clusters):
    min_, max_ = min(clusters[ncluster]), max(clusters[ncluster])
    s = ct.get_corner_f(random.randint(min_, max_))
    c = s
    k = 99999

    m_v = {ct.get_vertex(ct.previous_corner(c)): 1,
           ct.get_vertex(ct.next_corner(c)): 1}
    m_t = {}
    d = []
    n = 0
    while 1:
        if (not m_v.get(ct.get_vertex(c), 0)) and (min_ <= ct.get_triangle(c) < max_):
            m_v[ct.get_vertex(c)] = 1
            m_t[ct.get_triangle(c)] = 1

            d.append(ct.get_left_corner(c))
            d.append(ct.get_right_corner(c))
            n += 1

        if not d:
            break
        if n % k == 0:
            c = d.pop(0)
        else:
            c = d.pop()
        
    return m_v


def test_laced_ring(vertices, faces, cluster_size):
    vertices_faces = make_vertex_faces(vertices, faces)
    ct = cy_corner_table.CornerTable()
    ct.create_corner_from_vertex_face(vertices, faces, vertices_faces)
    clusters = clusterize_ct(ct, cluster_size)
    print clusters.keys()
    ecluster = {}
    for i in sorted(clusters):
        ncluster = expand_ring_into_cluster(ct, i, clusters)
        #print i, len(ncluster)
        ecluster.update(ncluster)

    colours = {}
    for v in xrange(len(vertices)):
        if ecluster.get(v, 0):
            colours[v] = (255, 0, 0)
        else:
            colours[v] = (255, 255, 255)
    writer = ply_writer.PlyWriter('/tmp/saida.ply')
    writer.from_faces_vertices_list(faces, vertices, colours)


def main():
    vertices, faces = read_ply(sys.argv[1])
    test_laced_ring(vertices, faces, int(sys.argv[2]))

if __name__ == '__main__' :
    main()