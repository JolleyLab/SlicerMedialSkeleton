#include "SkeletonToolCLP.h"

// Logic includes
#include "VTKMeshShortestDistance.h"
#include "VTKMeshHalfEdgeWrapper.h"

// VNL includes
#include <vnl/vnl_vector.h>
#include <vnl/vnl_cross.h>

// VTK includes
#include <vtkQuadricClustering.h>
#include <vtkSelectEnclosedPoints.h>
#include <vtkBoundingBox.h>
#include <vtkCellArray.h>
#include <vtkCellDataToPointData.h>
#include <vtkPolyData.h>
#include <vtkLODActor.h>
#include <vtkRenderer.h>
#include <vtkRenderWindow.h>
#include <vtkTriangleFilter.h>
#include <vtkCell.h>
#include <vtkCellData.h>
#include <vtkDoubleArray.h>
#include <vtkCleanPolyData.h>
#include <vtkPolyDataConnectivityFilter.h>
#include <vtkTriangle.h>
#include <vtkPolyDataNormals.h>

// MRML includes
#include "vtkMRMLModelStorageNode.h"
#include "vtkMRMLModelNode.h"

extern "C" {
#include <libqhull_r/libqhull_r.h>
}

// Use an anonymous namespace to keep class types and function names
// from colliding when module is used as shared object module.  Every
// thing should be in an anonymous namespace except for the module
// entry point, e.g. main()
//
namespace {


#ifndef vtkFloatingPointType
#define vtkFloatingPointType vtkFloatingPointType
    typedef float vtkFloatingPointType;
#endif

    inline vtkFloatingPointType TriangleArea(
        const vnl_vector_fixed<vtkFloatingPointType, 3> &A,
        const vnl_vector_fixed<vtkFloatingPointType, 3> &B,
        const vnl_vector_fixed<vtkFloatingPointType, 3> &C) {
      return 0.5 * vnl_cross_3d(B - A, C - A).magnitude();
    }


} // end of anonymous namespace

int main(int argc, char *argv[]) {
  PARSE_ARGS;

  // read the poly data
  vtkNew<vtkMRMLModelStorageNode> modelStorageNode;
  vtkNew<vtkMRMLModelNode> modelNode;
  modelStorageNode->SetFileName(inputSurface.c_str());
  if (!modelStorageNode->ReadData(modelNode)) {
    std::cerr << "Failed to read input model file " << inputSurface << std::endl;
    return EXIT_FAILURE;
  }

  // Load the input mesh
  vtkPolyData *bndraw = modelNode->GetPolyData();
  bndraw->BuildLinks();
  bndraw->BuildCells();

  // The raw boundary must be triangulated and cleaned
  vtkNew<vtkTriangleFilter> fTriangle;
  fTriangle->SetInputData(bndraw);
  fTriangle->Update();
  vtkNew<vtkCleanPolyData> fClean;

  fClean->SetInputConnection(fTriangle->GetOutputPort());
  fClean->SetTolerance(1e-4);
  fClean->Update();
  vtkPolyData *bnd = fClean->GetOutput();

  double bbBnd[6];
  bnd->GetBounds(bbBnd);
  printf("Bounding Box : %f %f %f %f %f %f\n", bbBnd[0], bbBnd[1], bbBnd[2], bbBnd[3], bbBnd[4], bbBnd[5]);
  vtkBoundingBox fBoundBox;
  fBoundBox.SetBounds(bbBnd);

  std::vector<double> points_3D;
  for (vtkIdType i = 0; i < bnd->GetNumberOfPoints(); i++) {
    points_3D.push_back(bnd->GetPoint(i)[0]);
    points_3D.push_back(bnd->GetPoint(i)[1]);
    points_3D.push_back(bnd->GetPoint(i)[2]);
  }

  // Create a temporary file where to store the points
  char *fnPoints = tmpnam(NULL);
  string fnVoronoiOutput = string(fnPoints) + "_voronoi.txt";
  cout << fnVoronoiOutput.c_str() << endl;
  FILE *output = fopen(fnVoronoiOutput.c_str(), "w");

  // https://github.com/ros-planning/geometric_shapes/blob/3c23af045de12eee725205f3e9e1c42aa1d53dc8/src/bodies.cpp#L934-L941
  static FILE* null = fopen("/dev/null", "w");

  int ndim = 3;
  int num_points = points_3D.size() / ndim;

  char qhull_cmd[] = "qhull v Qbb p Fv";
  qhT qh_qh;
  qhT* qh = &qh_qh;
  QHULL_LIB_CHECK
  qh_zero(qh, null);
  int exitcode = qh_new_qhull(qh, 3, num_points, points_3D.data(), false, qhull_cmd, output, null);

  if (exitcode != 0)
  {
    cerr << "Call to QVoronoi failed" << endl;
    return -1;
  }

  // Process qhull voronoi output

  // Load the file
  ifstream fin(fnVoronoiOutput.c_str());

  // Load the numbers
  size_t nv, np, junk;

  // First two lines
  fin >> junk;
  fin >> nv;

  vtkNew<vtkSelectEnclosedPoints> sel;
  sel->SetTolerance(xSearchTol);
  sel->Initialize(bnd);

  // Create an array of points
  vtkNew<vtkPoints> pts;
  pts->SetNumberOfPoints(nv);

  // Create an array of in/out flags
  bool *ptin = new bool[nv];

  // Progress bar
  cout << "Selecting points inside mesh (n = " << nv << ")" << endl;
  cout << "|         |         |         |         |         |" << endl;
  size_t next_prog_mark = nv / 50;

  for (size_t i = 0; i < nv; i++) {
    double x, y, z;
    fin >> x;
    fin >> y;
    fin >> z;
    pts->SetPoint(i, x, y, z);

    // Is this point outside of the bounding box
    if (xSearchTol > 0)
      ptin[i] = fBoundBox.ContainsPoint(x, y, z) && sel->IsInsideSurface(x, y, z);
    else
      ptin[i] = fBoundBox.ContainsPoint(x, y, z);

    if (i >= next_prog_mark) {
      cout << "." << flush;
      next_prog_mark += nv / 50;
    }
  }
  cout << "." << endl;

  // Read the number of cells
  fin >> np;

  // Progress bar
  cout << "Selecting faces using pruning criteria (n = " << np << ")" << endl;
  cout << "|         |         |         |         |         |" << endl;
  next_prog_mark = np / 50;

  // Create and configure Dijkstra's alg for geodesic distance
  VTKMeshHalfEdgeWrapper hewrap_geo(bnd);
  EuclideanDistanceMeshEdgeWeightFunction wfunc_geo;
  VTKMeshShortestDistance dijkstra_geo;
  dijkstra_geo.SetInputMesh(&hewrap_geo);
  dijkstra_geo.SetEdgeWeightFunction(&wfunc_geo);
  dijkstra_geo.ComputeGraph();

  // Create and configure Dijkstra's alg for edge counting
  VTKMeshHalfEdgeWrapper hewrap_edge(bnd);
  UnitLengthMeshEdgeWeightFunction wfunc_edge;
  VTKMeshShortestDistance dijkstra_edge;
  dijkstra_edge.SetInputMesh(&hewrap_edge);
  dijkstra_edge.SetEdgeWeightFunction(&wfunc_edge);
  dijkstra_edge.ComputeGraph();

  // Keep track of number pruned
  size_t npruned_geo = 0, npruned_edge = 0;

  // Create the polygons
  vtkNew<vtkCellArray> cells;

  // Allocate the output radius data array
  vtkNew<vtkDoubleArray> daRad;
  daRad->SetNumberOfComponents(1);
  daRad->SetName("Radius");

// Another array for prune strength
  vtkNew<vtkDoubleArray> daPrune;
  daPrune->SetNumberOfComponents(1);
  daPrune->SetName("Pruning Ratio");

// Another array for prune strength
  vtkNew<vtkDoubleArray> daGeod;
  daGeod->SetNumberOfComponents(1);
  daGeod->SetName("Geodesic");

  // iterating over cells
  for (size_t j = 0; j < np; j++) {
    bool isinf = false;
    bool isout = false;

    size_t m;
    fin >> m;
    m -= 2;
    vtkIdType ip1, ip2; // reading first two points of cell
    fin >> ip1;
    fin >> ip2;

    // reading rest of cells
    vtkIdType *ids = new vtkIdType[m];
    for (size_t k = 0; k < m; k++) {
      fin >> ids[k];

      // Is this point at infinity?
      if (ids[k] == 0) isinf = true; else ids[k]--;
      if (!ptin[ids[k]]) isout = true;
    }

    if (!isinf && !isout) {
      bool pruned = false;
      double r = 0, dgeo = 0;

      // Get the edge distance between generators
      dijkstra_edge.ComputeDistances(ip1, nDegrees);
      double elen = dijkstra_edge.GetVertexDistance(ip2);
      if (elen < nDegrees) {
        pruned = true;
        npruned_edge++;
      }
      else {
        // Get the Euclidean distance between generator points
        double ipDb1[3];
        double ipDb2[3];
        float ipFt1[3];
        float ipFt2[3];
        bnd->GetPoint(ip1, ipDb1);
        bnd->GetPoint(ip2, ipDb2);
        for (int i = 0; i < 3; i++) {
          ipFt1[i] = (float) ipDb1[i];
          ipFt2[i] = (float) ipDb2[i];
        }
        vnl_vector_fixed<float, 3> p1(ipFt1);
        vnl_vector_fixed<float, 3> p2(ipFt2);
        r = (p1 - p2).magnitude();
        /*std::cout << "p1: " << p1[0] << " " << p1[1] << " " << p1[2] << std::endl;
        std::cout << "p2: " << p2[0] << " " << p2[1] << " " << p2[2] << std::endl;
        std::cout << "r: " << r << std::endl;*/

        // The geodesic distance between generators should exceed d * xPrune;
        dijkstra_geo.ComputeDistances(ip1, r * xPrune + 1);

        // Get the distance
        dgeo = dijkstra_geo.GetVertexDistance(ip2);

        // If the geodesic is too short, don't insert point
        if (dgeo < r * xPrune) {
          pruned = true;
          npruned_geo++;
        }
      }

      if (!pruned) {
        // add the cell
        cells->InsertNextCell(m, ids);
        daRad->InsertNextTuple(&r);
        daGeod->InsertNextTuple(&dgeo);
        double ratio = dgeo / r;
        daPrune->InsertNextTuple(&ratio);
      }
    }

    if (j >= next_prog_mark) {
      cout << "." << flush;
      next_prog_mark += np / 50;
    }

    delete[] ids;
  }

  cout << "." << endl;
  cout << "Edge contraint pruned " << npruned_edge << " faces." << endl;
  cout << "Geodesic to Euclidean distance ratio contraint (" << xPrune << ") pruned " << npruned_geo << " faces."
       << endl;

  // Clean up files
  if (fin.is_open()) {
    fin.close();
    remove(fnVoronoiOutput.c_str());
  }
  remove(fnPoints);

  // Create the vtk poly data
  vtkNew<vtkPolyData> skel;
  skel->SetPoints(pts);
  skel->SetPolys(cells);
  skel->GetCellData()->AddArray(daRad);
  skel->GetCellData()->AddArray(daGeod);
  skel->GetCellData()->AddArray(daPrune);
  skel->BuildCells();
  skel->BuildLinks();

  // Drop the singleton points from the diagram (points not in any cell)
  vtkNew<vtkCleanPolyData> fltClean;
  fltClean->SetInputData(skel);
  fltClean->Update();
  cout << "Clean filter: trimmed "
       << skel->GetNumberOfPoints() << " vertices to "
       << fltClean->GetOutput()->GetNumberOfPoints() << endl;


  // The output from the next branch
  vtkPolyData *polySave = fltClean->GetOutput();

  // Compute the connected components
  if (nComp > 0) {
    vtkNew<vtkPolyDataConnectivityFilter> fltConnect;
    fltConnect->SetInputData(fltClean->GetOutput());

    if (nComp == 1)
      fltConnect->SetExtractionModeToLargestRegion();
    else {
      fltConnect->SetExtractionModeToSpecifiedRegions();
      fltConnect->InitializeSpecifiedRegionList();
      for (int rr = 0; rr < nComp; rr++)
        fltConnect->AddSpecifiedRegion(rr);
    }

    fltConnect->ScalarConnectivityOff();
    fltConnect->Update();

    // Don't see why this is necessary, but Connectivity filter does not remove points,
    // just faces. So we need another clear filter
    vtkNew<vtkCleanPolyData> fltWhy;
    fltWhy->SetInputData(fltConnect->GetOutput());
    fltWhy->Update();

    cout << "Connected component constraint pruned "
         << polySave->GetNumberOfCells() - fltWhy->GetOutput()->GetNumberOfCells() << " faces and "
         << polySave->GetNumberOfPoints() - fltWhy->GetOutput()->GetNumberOfPoints() << " points." << endl;
    polySave = fltWhy->GetOutput();
  }

  // Convert the cell data to point data
  vtkNew<vtkCellDataToPointData> c2p;
  c2p->SetInputData(polySave);
  c2p->PassCellDataOn();
  c2p->Update();
  vtkPolyData *final = c2p->GetPolyDataOutput();

  // Compute mean, median thickness?
  double int_area = 0.0, int_thick = 0.0;
  vtkDataArray *finalRad = final->GetCellData()->GetArray("Radius");
  for (vtkIdType i = 0; i < final->GetNumberOfCells(); i++) {
    double r = finalRad->GetTuple1(i);
    //std::cout << "r: " << r << std::endl;
    vtkCell *c = final->GetCell(i);
    if (c->GetNumberOfPoints() == 3) {
      vtkIdType p1Id = c->GetPointId(0);
      vtkIdType p2Id = c->GetPointId(1);
      vtkIdType p3Id = c->GetPointId(2);
      double p1d[3];
      double p2d[3];
      double p3d[3];
      float p1f[3];
      float p2f[3];
      float p3f[3];
      final->GetPoint(p1Id, p1d);
      final->GetPoint(p2Id, p2d);
      final->GetPoint(p3Id, p3d);
      for (int i = 0; i < 3; i++) {
        p1f[i] = (float) p1d[i];
        p2f[i] = (float) p2d[i];
        p3f[i] = (float) p3d[i];
      }
      vnl_vector_fixed<float, 3> p1(p1f);
      vnl_vector_fixed<float, 3> p2(p2f);
      vnl_vector_fixed<float, 3> p3(p3f);
      double a = fabs(TriangleArea(p1, p2, p3));
      //std::cout << "a: " << a << std::endl;
      int_area += a;
      int_thick += r * a;
    }
  }
  cout << "Surface area: " << int_area << endl;
  cout << "Mean thickness: " << int_thick / int_area << endl;

  vtkPolyData *skelfinal = c2p->GetPolyDataOutput();

  // Quadric clustering
  if (nBins > 0) {
    // Calculate appropriate bin size
    double bbBnd[6];
    skelfinal->GetBounds(bbBnd);
    vtkBoundingBox fbb;
    fbb.SetBounds(bbBnd);
    double binsize = fbb.GetMaxLength() / nBins;

    vtkNew<vtkQuadricClustering> fCluster;
    fCluster->SetNumberOfDivisions(
        ceil(fbb.GetLength(0) / binsize),
        ceil(fbb.GetLength(1) / binsize),
        ceil(fbb.GetLength(2) / binsize));
    fCluster->SetInputData(c2p->GetPolyDataOutput());
    fCluster->SetCopyCellData(1);
    fCluster->Update();

    printf("QuadClustering (%d x %d x %d blocks) :\n",
           fCluster->GetNumberOfXDivisions(),
           fCluster->GetNumberOfYDivisions(),
           fCluster->GetNumberOfZDivisions());
    printf("  Input mesh: %d points, %d cells\n",
           (int) skelfinal->GetNumberOfPoints(),
           (int) skelfinal->GetNumberOfCells());
    printf("  Output mesh: %d points, %d cells\n",
           (int) fCluster->GetOutput()->GetNumberOfPoints(),
           (int) fCluster->GetOutput()->GetNumberOfCells());

    // Convert cell data to point data again
    vtkNew<vtkCellDataToPointData> c2p;
    c2p->SetInputData(fCluster->GetOutput());
    c2p->PassCellDataOn();
    c2p->Update();
    skelfinal = c2p->GetPolyDataOutput();
  }

  // orienting normals
  vtkNew<vtkPolyDataNormals> polyDataNormals;
  polyDataNormals->SetInputData(skelfinal);
  polyDataNormals->ConsistencyOn();
  polyDataNormals->AutoOrientNormalsOn();
  polyDataNormals->Update();
  skelfinal = polyDataNormals->GetOutput();

  vtkNew<vtkMRMLModelNode> outputModelNode;
  outputModelNode->SetAndObservePolyData(skelfinal);
  vtkNew<vtkMRMLModelStorageNode> outputModelStorageNode;
  outputModelStorageNode->SetFileName(outputSurface.c_str());
  if (!outputModelStorageNode->WriteData(outputModelNode)) {
    std::cerr << "Failed to write output model file " << outputSurface << std::endl;
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
