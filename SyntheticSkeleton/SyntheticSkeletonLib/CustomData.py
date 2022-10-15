from SyntheticSkeletonLib.Constants import *
from SyntheticSkeletonLib.Utils import writePolydata
import numpy as np
import slicer
import qt
import vtk
import logging


class CustomInformationReader(object):

  @property
  def polydata(self):
    model = self.skeletonModel.getInputModelNode()
    return model.GetPolyData() if model is not None else None

  def __init__(self, skeletonModel):
    self.skeletonModel = skeletonModel

  def hasCustomData(self):
    fielddata = self.polydata.GetFieldData()
    tagStr = fielddata.GetAbstractArray("TagName")
    return tagStr and tagStr.GetNumberOfValues() > 0

  def readCustomData(self):
    fielddata = self.polydata.GetFieldData()

    self._readCustomPointLabels(fielddata)
    self._readCustomDataTriLabel(fielddata)
    self._readCustomDataPoints(fielddata)
    self._readCustomDataTri(fielddata)

  def _readCustomPointLabels(self, fielddata):
    tagDBL = fielddata.GetArray("TagInfo")
    tagStr = fielddata.GetAbstractArray("TagName")

    if not tagStr:
      return

    logging.debug(f"string size {tagStr.GetNumberOfValues()}")

    j = 0
    for i in range(0, tagDBL.GetNumberOfValues() - 1, 5):
      n = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", tagStr.GetValue(j))
      n.SetAttribute(ATTR_TYPE_INDEX, str(int(float(tagDBL.GetValue(i)))))
      n.SetAttribute(ATTR_ANATOMICAL_INDEX, str(int(float(tagDBL.GetValue(i + 1)))))
      n.SetAttribute("ModuleName", MODULE_NAME)

      dNode = n.GetDisplayNode()
      dNode.SetSelectedColor([
        tagDBL.GetValue(i + 2) / 255.0,
        tagDBL.GetValue(i + 3) / 255.0,
        tagDBL.GetValue(i + 4) / 255.0
      ])
      dNode.SetPointLabelsVisibility(False)
      dNode.SetPropertiesLabelVisibility(False)
      self.skeletonModel.addPointLabel(n)
      j += 1

  def _readCustomDataPoints(self, fielddata):
    ptsDBL = fielddata.GetArray("TagPoints")
    if not ptsDBL:
      return

    for i in range(0, ptsDBL.GetNumberOfValues(), 7):
      pointLabel = self.skeletonModel.pointLabels[int(ptsDBL.GetValue(i + 6))]
      markupsNode = pointLabel.markupsNode
      markupsNode.AddControlPoint(vtk.vtkVector3d(ptsDBL.GetValue(i), ptsDBL.GetValue(i + 1), ptsDBL.GetValue(i + 2)))

  def _readCustomDataTriLabel(self, fielddata):
    tagTriDBL = fielddata.GetArray("LabelTriangleColor")
    tagTriStr = fielddata.GetAbstractArray("LabelTriangleName")
    if not tagTriStr:
      return

    logging.debug(f"label triangle size {tagTriStr.GetNumberOfValues()}")

    j = 0
    for i in range(0, tagTriDBL.GetNumberOfValues(), 3):
      triNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode", tagTriStr.GetValue(j))
      triNode.SetAttribute("ModuleName", MODULE_NAME)
      triNode.SetAttribute(ATTR_COLOR,
                     str(qt.QColor(tagTriDBL.GetValue(i), tagTriDBL.GetValue(i + 1), tagTriDBL.GetValue(i + 2))))
      triNode.SetAttribute("Type", "TriangleLabel")
      self.skeletonModel.addTriangleLabel(triNode)
      j += 1

  def _readCustomDataTri(self, fielddata):
    triDBL = fielddata.GetArray("TagTriangles")
    if not triDBL:
      return

    for i in range(0, triDBL.GetNumberOfValues(), 16):
      p1 = self.skeletonModel.points[int(triDBL.GetValue(i + 3))]
      p2 = self.skeletonModel.points[int(triDBL.GetValue(i + 8))]
      p3 = self.skeletonModel.points[int(triDBL.GetValue(i + 13))]

      selectedPoints = [(p1.markupsNode.GetID(), p1.pointID),
                        (p2.markupsNode.GetID(), p2.pointID),
                        (p3.markupsNode.GetID(), p3.pointID)]
      self.skeletonModel.addTriangle(
        selectedPoints,
        self.skeletonModel.triangleLabels[int(triDBL.GetValue(i + 15))],
        checkNormals=False
      )


class CustomInformationWriter(object):

  @property
  def triangleLabels(self):
    return self.skeletonModel.triangleLabels

  @property
  def pointLabels(self):
    return self.skeletonModel.pointLabels

  @property
  def triangles(self):
    return self.skeletonModel.triangles

  @property
  def points(self):
    return self.skeletonModel.points

  @property
  def edges(self):
    return self.skeletonModel.edges

  @property
  def labelData(self):
    return self.skeletonModel.labelData

  @property
  def polydata(self):
    model = self.skeletonModel.getInputModelNode()
    return model.GetPolyData() if model is not None else None

  def __init__(self, data):
    self.skeletonModel = data

  def writeCustomDataToFile(self, outputFilePath):
    finalPolyData = self.createPolyDataFromCustomData(self.polydata)
    writePolydata(finalPolyData, outputFilePath, useRAS=True)

  def createPolyDataFromCustomData(self, polydata):
    finalPolyData = vtk.vtkPolyData()
    finalPolyData.DeepCopy(polydata)
    fielddata = finalPolyData.GetFieldData()

    self._writeCustomDataLabel(fielddata)
    self._writeCustomDataTag(fielddata)
    self._writeCustomDataPoints(fielddata)
    self._writeCustomDataTriLabel(fielddata)
    self._writeCustomDataTri(fielddata)
    self._writeCustomDataEdge(fielddata)

    finalPolyData.SetFieldData(fielddata)
    return finalPolyData

  def _writeCustomDataLabel(self, fielddata):
    if fielddata.GetArray("Label"):
      fielddata.RemoveArray("Label")

    labelData = np.zeros((self.polydata.GetNumberOfPoints(),), dtype=float)
    for pt in self.points:
      seq, _ = self.skeletonModel.getClosestVertexAndRadius(pt.pos)
      labelData[seq] = pt.typeIndex

    fltArray1 = vtk.vtkFloatArray()
    fltArray1.SetName("Label")

    for label in labelData:
      fltArray1.InsertNextValue(label)

    if len(labelData) != 0:
      fielddata.AddArray(fltArray1)

  def _writeCustomDataTag(self, fielddata):
    if fielddata.GetArray("TagInfo"):
      fielddata.RemoveArray("TagInfo")
    if fielddata.GetArray("TagName"):
      fielddata.RemoveArray("TagName")

    fltArray5 = vtk.vtkFloatArray()
    fltArray5.SetName("TagInfo")
    strArray1 = vtk.vtkStringArray()
    strArray1.SetName("TagName")

    for pointLabel in self.pointLabels:
      fltArray5.InsertNextValue(pointLabel.typeIndex)
      fltArray5.InsertNextValue(pointLabel.anatomicalIndex)

      color = pointLabel.markupsNode.GetDisplayNode().GetSelectedColor()
      fltArray5.InsertNextValue(color[0] * 255)
      fltArray5.InsertNextValue(color[1] * 255)
      fltArray5.InsertNextValue(color[2] * 255)

      strArray1.InsertNextValue(pointLabel.name)

    if len(self.pointLabels) != 0:
      fielddata.AddArray(fltArray5)
      fielddata.AddArray(strArray1)

  def _writeCustomDataTriLabel(self, fielddata):
    if fielddata.GetArray("LabelTriangleName"):
      fielddata.RemoveArray("LabelTriangleName")
    if fielddata.GetArray("LabelTriangleColor"):
      fielddata.RemoveArray("LabelTriangleColor")

    strArray2_1 = vtk.vtkStringArray()
    strArray2_1.SetName("LabelTriangleName")
    fltArray2_1 = vtk.vtkFloatArray()
    fltArray2_1.SetName("LabelTriangleColor")

    for i in range(len(self.triangleLabels)):
      strArray2_1.InsertNextValue(self.triangleLabels[i].name)
      qc = qt.QColor(self.triangleLabels[i].color)
      fltArray2_1.InsertNextValue(qc.red())
      fltArray2_1.InsertNextValue(qc.green())
      fltArray2_1.InsertNextValue(qc.blue())

    if len(self.triangleLabels) != 0:
      fielddata.AddArray(strArray2_1)
      fielddata.AddArray(fltArray2_1)

  def _writeCustomDataPoints(self, fielddata):
    if fielddata.GetArray("TagPoints"):
      fielddata.RemoveArray("TagPoints")

    fltArray4 = vtk.vtkFloatArray()
    fltArray4.SetName("TagPoints")
    for i in range(len(self.points)):
      pt = self.points[i]
      fltArray4.InsertNextValue(pt.pos[0])
      fltArray4.InsertNextValue(pt.pos[1])
      fltArray4.InsertNextValue(pt.pos[2])
      seq, radius = self.skeletonModel.getClosestVertexAndRadius(pt.pos)
      fltArray4.InsertNextValue(radius)
      fltArray4.InsertNextValue(seq)
      fltArray4.InsertNextValue(pt.typeIndex)
      pointLabel = self.skeletonModel.findPointLabel(pt.markupsNode)
      fltArray4.InsertNextValue(self.pointLabels.index(pointLabel))
    if len(self.points) != 0:
      fielddata.AddArray(fltArray4)

  def _writeCustomDataEdge(self, fielddata):
    if fielddata.GetArray("TagEdges"):
      fielddata.RemoveArray("TagEdges")
    fltArray3 = vtk.vtkFloatArray()
    fltArray3.SetName("TagEdges")

    # create dummy array to fill in vtk fields
    from SyntheticSkeletonLib.Utils import pairNumber
    maxId = pairNumber(len(self.points), len(self.points))

    from SyntheticSkeletonLib.SkeletonModel import Edge
    vectorTagEdges = np.zeros((maxId+1,), dtype=Edge)
    for key, val in self.edges.items():
      vectorTagEdges[key] = val

    for i in range(len(vectorTagEdges)):
      edge = vectorTagEdges[i]
      if not edge:
        for j in range(5):
          fltArray3.InsertNextValue(0)
      else:
        fltArray3.InsertNextValue(edge.ptId1)
        fltArray3.InsertNextValue(edge.ptId2)
        fltArray3.InsertNextValue(edge.seq)
        fltArray3.InsertNextValue(edge.numEdge)
        fltArray3.InsertNextValue(edge.constrain)
    if len(vectorTagEdges) != 0:
      fielddata.AddArray(fltArray3)

  def _writeCustomDataTri(self, fielddata):
    if fielddata.GetArray("TagTriangles"):
      fielddata.RemoveArray("TagTriangles")

    fltArray2 = vtk.vtkFloatArray()
    fltArray2.SetName("TagTriangles")
    for i in range(len(self.triangles)):
      tri = self.triangles[i]
      for ptRef in tri.points:
        pt = self.skeletonModel.findPointByScriptedNode(ptRef)
        fltArray2.InsertNextValue(pt.pos[0])
        fltArray2.InsertNextValue(pt.pos[1])
        fltArray2.InsertNextValue(pt.pos[2])
        fltArray2.InsertNextValue(self.points.index(pt))
        seq, _ = self.skeletonModel.getClosestVertexAndRadius(pt.pos)
        fltArray2.InsertNextValue(seq)
      triangleLabel = self.skeletonModel.findTriangleLabel(tri.triangleLabel)
      fltArray2.InsertNextValue(self.triangleLabels.index(triangleLabel))
    if len(self.triangles) != 0:
      fielddata.AddArray(fltArray2)
