#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import cy_corner_table
import ply_reader
import ply_writer
import cy_sorter
import wrl_writer

def ply2wrl(ply_filename, wrl_filename):
    vertices = []
    faces = []
    reader = ply_reader.PlyReader(ply_filename)
    for evt, data in reader.read():
        if evt == ply_reader.EVENT_VERTEX:
            vertices.append(data)

        elif evt == ply_reader.EVENT_FACE:
            faces.append(data)

    writer = wrl_writer.WrlWriter(wrl_filename)
    writer.from_faces_vertices_list(faces, vertices)

def main():
    import sys
    ply2wrl(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
