#ifndef __MeshTraversal_h_
#define __MeshTraversal_h_

#include <vector>
#include <set>


using namespace std;

// Constant used for unreasonable size_t objects
#define NOID 0xffffffff

/**
 * A representation of a triangle in a mesh
 */
struct Triangle
{
  // Index of the triangle's vertices
  size_t vertices[3];

  // Index of the neighbors
  size_t neighbors[3];

  // Optional label of the triangle. Will be propagated to children
  size_t label;

  // Each edge is associated with an index of the vertex opposite to it.
  // This value tells us for each edge its index in the adjacent triangle
  short nedges[3];

  // Initializes to dummy values
  Triangle()
    {
    vertices[0] = vertices[1] = vertices[2] = NOID;
    neighbors[0] = neighbors[1] = neighbors[2] = NOID;
    nedges[0] = nedges[1] = nedges[2] = -1;
    label = NOID;
    }
};

#endif
