#!/usr/bin/env python
# -*- coding: UTF-8 -*-

class WrlWriter(object):
    def __init__(self, filename):
        self.filename = filename

    def write_header(self, wrl_file):
        wrl_file.write ("""#VRML V2.0 utf8

NavigationInfo {
    type [ "EXAMINE", "ANY" ]
}
Transform {
  scale 1 1 1
  translation 0 0 0
  children
  [
    Shape
    {
      geometry IndexedFaceSet
      {
        creaseAngle .5
        solid FALSE
        coord Coordinate
        {""")

    def write_vertices(self, wrl_file, vertices):
        wrl_file.write('point\n[\n')
        for v in range(len(vertices)):
            wrl_file.write(' '.join(['%f' % i for i in vertices[v][:3]]) + ',\n')
        wrl_file.write(']\n}')

    def write_faces(self, wrl_file, faces):
        wrl_file.write('coordIndex\n [ \n')
        for vx, vy, vz in faces:
            wrl_file.write('%d, %d, %d, -1,\n' % (vx, vy, vz))
        wrl_file.write(']\n}')


    def from_faces_vertices_list(self, faces, vertices):
        with file(self.filename, 'w') as wrl_file:
            self.write_header(wrl_file)
            self.write_vertices(wrl_file, vertices)
            self.write_faces(wrl_file, faces)

            wrl_file.write("""      appearance Appearance
      {
        material Material
        {
	       ambientIntensity 0.2
	       diffuseColor 0.9 0.9 0.9
	       specularColor .1 .1 .1
	       shininess .5
        }
      }
    }
  ]
}
""")
