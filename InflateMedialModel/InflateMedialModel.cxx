#include "InflateMedialModelCLP.h"

// CMREP includes
#include "MedialException.h"
#include "MeshTraversal.h"

// VNL includes
#include <vnl/vnl_math.h>
#include <vnl/vnl_sparse_matrix.h>
#include <vnl/vnl_vector_fixed.h>
#include <vnl/vnl_cross.h>

// VTK includes
#include <vtkCellArray.h>
#include <vtkCellDataToPointData.h>
#include <vtkPolyData.h>
#include <vtkPointData.h>

// MRML includes
#include "vtkMRMLModelStorageNode.h"
#include "vtkMRMLModelNode.h"


using namespace std;

// Use an anonymous namespace to keep class types and function names
// from colliding when module is used as shared object module.  Every
// thing should be in an anonymous namespace except for the module
// entry point, e.g. main()
//
namespace {

template<class T>
unsigned int count_nnz(vnl_sparse_matrix<T> &mat)
{
  unsigned int nnz = 0;
  for(unsigned int i = 0; i < mat.rows(); i++)
  {
    auto &r = mat.get_row(i);
    for(unsigned int j = 0; j < r.size(); j++)
    {
      if(r[j].second != 0.0)
        nnz++;
    }
  }
  return nnz;
}

} // end of anonymous namespace


int main(int argc, char *argv[]) {
  PARSE_ARGS;
  // This inflation code accepts non-mesh medial surfaces, i.e., medial surfaces with branches

  // read the poly data
  vtkNew<vtkMRMLModelStorageNode> modelStorageNode;
  vtkNew<vtkMRMLModelNode> modelNode;
  modelStorageNode->SetFileName(inputSurface.c_str());
  if (!modelStorageNode->ReadData(modelNode)) {
    std::cerr << "Failed to read input model file " << inputSurface << std::endl;
    return EXIT_FAILURE;
  }

  // Convert it into a triangle mesh
  vtkPolyData *pd = modelNode->GetPolyData();
  vtkDataArray *alab = pd->GetPointData()->GetArray("Label");
  unsigned int nv = (unsigned int) pd->GetNumberOfPoints();

  // An edge is a pair of vertices, always stored in sorted order
  typedef std::pair<unsigned int, unsigned int> Edge;

  // A reference to a triangle edge (tri index, edge index, forward/backward)
  typedef std::tuple<unsigned int, unsigned int, bool> TriEdgeRef;

  // Each edge is associated with some number of triangles
  typedef std::map<Edge, std::list<TriEdgeRef> > EdgeTriMap;

  // Edge-triangle map
  EdgeTriMap etm;

  // List of duplicate triangles
  std::vector<Triangle> tdup;

  // List of triangle normals
  typedef vnl_vector_fixed<double, 3> Vec3;
  std::vector<Vec3> tnorm;

  // Find all the edges in the mesh
  for(unsigned int i = 0; i < pd->GetNumberOfCells(); i++)
  {
    // Read the cell
    vtkCell *c = pd->GetCell(i);
    if(c->GetNumberOfPoints() != 3)
      throw MedialModelException("Bad cell in input");

    // Create duplicates of the triangle with opposite windings
    Triangle t1;
    t1.vertices[0] = c->GetPointId(0);
    t1.vertices[1] = c->GetPointId(1);
    t1.vertices[2] = c->GetPointId(2);
    tdup.push_back(t1);

    Triangle t2;
    t2.vertices[0] = c->GetPointId(2);
    t2.vertices[1] = c->GetPointId(1);
    t2.vertices[2] = c->GetPointId(0);
    tdup.push_back(t2);

    // Compute the normals of the two triangles
    Vec3 A(pd->GetPoint(c->GetPointId(0)));
    Vec3 B(pd->GetPoint(c->GetPointId(1)));
    Vec3 C(pd->GetPoint(c->GetPointId(2)));
    Vec3 N = vnl_cross_3d(B-A, C-A).normalize();

    tnorm.push_back(N);
    tnorm.push_back(-N);
  }

  // Find edges across the duplicate triangles
  for(unsigned int i = 0; i < tdup.size(); i++)
  {
    for(unsigned int k = 0; k < 3; k++)
    {
      size_t v1 = tdup[i].vertices[(k+1) % 3];
      size_t v2 = tdup[i].vertices[(k+2) % 3];
      Edge ek = make_pair(min(v1,v2), max(v1,v2));

      // Add the triangle to this edge, marking it as either forward-traversed
      // or backward traversed.
      etm[ek].push_back(std::make_tuple(i, k, v1 > v2));
    }
  }

  // For each edge, find the triangles that are adjacent across the edge. Adjacent
  // triangles must traverse the edge in opposite order.
  for(auto &eit : etm)
  {
    // Get the edge vector direction
    Vec3 e_X1(pd->GetPoint(eit.first.first));
    Vec3 e_X2(pd->GetPoint(eit.first.second));

    for(auto &tref : eit.second)
    {
      // Get the normal of the current triangle
      unsigned int i_tri = std::get<0>(tref);
      unsigned int i_tri_edge_idx = std::get<1>(tref);
      bool winding = std::get<2>(tref);

      const Vec3 &N = tnorm[i_tri];
      Vec3 Z = (e_X2 - e_X1).normalize();
      if(!winding)
        Z = -Z;
      Vec3 X = vnl_cross_3d(Z, N);

      // Find the triangle that is closest by converting each opposite-winded triangle
      // to an angle and selecting the one with the minimum angle
      unsigned int opp_tri = NOID, opp_tri_edge_idx = -1;
      double min_angle = 0.0;
      for(auto &tref_test : eit.second)
      {
        // Only consider opposite winding
        if(std::get<2>(tref_test) != std::get<2>(tref))
        {
          // Find the 'X' of the test triangle
          unsigned int i_tri_test = std::get<0>(tref_test);
          const Vec3 &N_test = -tnorm[i_tri_test];
          Vec3 X_test = vnl_cross_3d(Z, N_test);

          // Find the angle with the current triangle.
          double a_test = (i_tri / 2 == i_tri_test / 2)
                          ? vnl_math::twopi
                          : atan2(dot_product(X_test, N), dot_product(X_test, X));
          if(a_test <= 0.0)
            a_test += vnl_math::twopi;

          printf("Angle of triangle %d with triangle %d over edge (%d,%d) is %f\n",
                 i_tri, i_tri_test, eit.first.first, eit.first.second, a_test);

          // Is this the best match
          if(opp_tri == NOID || a_test < min_angle)
          {
            opp_tri = i_tri_test;
            opp_tri_edge_idx = std::get<1>(tref_test);
            min_angle = a_test;
          }
        }
      }

      // We can now mark the neighbor of the triangle across this edge
      tdup[i_tri].neighbors[i_tri_edge_idx] = opp_tri;
      tdup[i_tri].nedges[i_tri_edge_idx] = (short) opp_tri_edge_idx;

      printf("Triangle %d matched to triangle %d\n", i_tri, opp_tri);
    }
  }

  // Create a vertex adjacency matrix. The rows/columns refer to the triangle vertices
  // which are at this point all considered to be disjoint points. When the adjacency
  // matrix contains 1, this means that the two vertices are actually the same point
  vnl_sparse_matrix<int> tv_adj(tdup.size() * 3, tdup.size() * 3);

  // Visit each edge in each triangle and match the vertices with the opposite edge
  // in the opposite triangle
  for(unsigned int i = 0; i < tdup.size(); i++)
  {
    for(unsigned int k = 0; k < 3; k++)
    {
      // Add identity element to matrix
      tv_adj(i * 3  + k, i * 3 + k) = 1;

      // Take triangle that's opposite
      unsigned int i_opp = tdup[i].neighbors[k];
      if(i_opp == NOID)
        throw MedialModelException("Triangle missing neighbor");

      // Set the matches
      unsigned int k_opp = tdup[i].nedges[k];
      unsigned int v1 = (k + 1) % 3, v2 = (k + 2) % 3;
      unsigned int v1_opp = (k_opp + 1) % 3, v2_opp = (k_opp + 2) % 3;

      tv_adj(i * 3 + v1, i_opp * 3 + v2_opp) = 1;
      tv_adj(i * 3 + v2, i_opp * 3 + v1_opp) = 1;
    }
  }

  // Find the connected components in the adjacency matrix. A lazy way to do this is to take powers of the
  // matrix until it converges.
  unsigned int nnz_last = count_nnz(tv_adj);
  printf("Adjacency matrix, nnz = %d\n", nnz_last);
  vnl_sparse_matrix<int> tv_adj_pow = tv_adj * tv_adj;
  while(count_nnz(tv_adj_pow) > nnz_last)
  {
    nnz_last = count_nnz(tv_adj_pow);
    tv_adj_pow = tv_adj_pow * tv_adj;
    printf("Adjacency multiplication, nnz = %d\n", nnz_last);
  }

  // Go through and remap the disjoint vertices to new vertices
  std::vector<unsigned int> vnew(tdup.size() * 3, NOID);
  unsigned int vcurr = 0;
  for(unsigned int i = 0; i < tdup.size() * 3; i++)
  {
    if(vnew[i] == NOID)
    {
      // Assign a new vertex ID to this vertex
      vnew[i] = vcurr;

      // Assign it to every other vertex in its row
      auto &row = tv_adj_pow.get_row(i);
      for(unsigned int j = 0; j < row.size(); j++)
      {
        if(vnew[row[j].first] != NOID && vnew[row[j].first] != vcurr)
          throw MedialModelException("Vertex traversal logic violation");

        vnew[row[j].first] = vcurr;
      }
      vcurr++;
    }
  }

  // Now we have a valid mesh structure in place. We can store this into a proper
  // triangle array
  vnl_matrix<unsigned int> m_tri(tdup.size(), 3);

  // We also need to compute the positions of the new vertices, i.e., by pushing them out
  // along the outward normals. We initialize each point to its original mesh location and
  // then add to the vertex all the normals of all the triangles that contain it
  vnl_matrix<double> m_pt(vcurr, 3), m_pt_offset(vcurr, 3);
  std::vector<unsigned int> valence(vcurr, 0);

  // Create the medial index array - this is just the original medial vertex
  vnl_vector<int> m_mindex(vcurr);

  // First pass through triangles, assigning new vertices and vertex coordinates
  for(unsigned int i = 0; i < tdup.size(); i++)
  {
    // Compute the triangle normal and center
    Vec3 P[] = {
        Vec3(pd->GetPoint(tdup[i].vertices[0])),
        Vec3(pd->GetPoint(tdup[i].vertices[1])),
        Vec3(pd->GetPoint(tdup[i].vertices[2])) };

    Vec3 N = vnl_cross_3d(P[1]-P[0], P[2]-P[0]).normalize();
    Vec3 C = (P[0] + P[1] + P[2])/3.0;

    for(unsigned int k = 0; k < 3; k++)
    {
      // Assign the new vertex
      m_tri(i,k) = vnew[i * 3 + k];

      // Get the coordinate of this vertex
      m_pt.set_row(m_tri(i,k), P[k]);

      // Add up the valence of this vertex
      valence[m_tri(i,k)]++;

      // Add up to the shift vector
      m_pt_offset.set_row(m_tri(i,k), m_pt_offset.get_row(m_tri(i,k)) + N);

      // Set the medial index (original index before inflation)
      m_mindex[m_tri(i,k)] = tdup[i].vertices[k];
    }
  }

  // Offset the vertices
  for(unsigned int j = 0; j < vcurr; j++)
    m_pt.set_row(j, m_pt.get_row(j) + rad * m_pt_offset.get_row(j) / valence[j]);

  vtkNew<vtkPolyData> vmb;

  vtkNew<vtkCellArray> cells;
  for (unsigned int i = 0; i < m_tri.rows(); i++)
  {
    cells->InsertNextCell(3);
    for (unsigned int a = 0; a < 3; a++)
      cells->InsertCellPoint(m_tri(i, a));
  }
  vmb->SetPolys(cells);
  assert(m_pt.columns() == 3);
  vtkNew<vtkPoints> pts;
  pts->SetNumberOfPoints(m_pt.rows());
  for (int i = 0; i < m_pt.rows(); i++)
    pts->SetPoint(i, m_pt(i, 0), m_pt(i, 1), m_pt(i, 2));

  vmb->SetPoints(pts);

  vtkNew<vtkIntArray> arr;
  arr->SetNumberOfComponents(1);
  arr->SetNumberOfTuples(m_mindex.size());
  arr->SetName("MedialIndex");
  // Update the points
  for (int i = 0; i < m_mindex.size(); i++)
    arr->SetTuple1(i, m_mindex[i]);
  vmb->GetPointData()->AddArray(arr);

  vtkNew<vtkMRMLModelNode> outputModelNode;
  outputModelNode->SetAndObservePolyData(vmb);
  vtkNew<vtkMRMLModelStorageNode> outputModelStorageNode;
  outputModelStorageNode->SetFileName(outputSurface.c_str());
  if (!outputModelStorageNode->WriteData(outputModelNode)) {
    std::cerr << "Failed to write output model file " << outputSurface << std::endl;
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
