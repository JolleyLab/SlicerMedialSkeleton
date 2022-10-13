import qt
import slicer
import vtk
from slicer.util import VTKObservationMixin
from SyntheticSkeletonLib.Utils import *
from SyntheticSkeletonLib.Constants import *
from collections import OrderedDict
import logging
from dataclasses import dataclass



SyntheticSkeletonModels = {}


def getSyntheticSkeletonModel(syntheticSkeletonNode):
  if syntheticSkeletonNode is None:
    return None

  if syntheticSkeletonNode in SyntheticSkeletonModels.keys():
    return SyntheticSkeletonModels[syntheticSkeletonNode]

  syntheticSkeletonModel = SyntheticSkeletonModel()
  syntheticSkeletonModel.setSyntheticSkeletonNode(syntheticSkeletonNode)

  SyntheticSkeletonModels[syntheticSkeletonNode] = syntheticSkeletonModel
  return syntheticSkeletonModel


class SyntheticSkeletonModel(VTKObservationMixin):

  def __init__(self):
    VTKObservationMixin.__init__(self)
    self.syntheticSkeletonNode = None

    # List of PointLabel objects, one for each point list
    self.pointLabels = []

    # List of TriangleLabel objects, one for each triangle label
    self.triangleLabels = []

    # List of Triangle objects, one for each triangle
    self.triangles = []

    # List of Point objects, one for each control point
    self.points = []

    # List of Edge objects, one for each control point
    self.edges = OrderedDict()

    self.locator = None

    self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAboutToBeRemovedEvent, self.onNodeRemoved)

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeRemoved(self, caller, event, node):
    if self.syntheticSkeletonNode and node is self.syntheticSkeletonNode:
      self.deleteData()
      self.removeObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAboutToBeRemovedEvent, self.onNodeRemoved)

  def deleteData(self):
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    parentFolderId = None
    for triIdx in reversed(range(len(self.triangleLabels))):
      triangleLabel = self.triangleLabels[triIdx]
      nodeItemId = shNode.GetItemByDataNode(triangleLabel.scriptedNode)
      parentFolderId = shNode.GetItemParent(nodeItemId)
      slicer.mrmlScene.RemoveNode(triangleLabel.scriptedNode)
    self.triangleLabels = []
    if parentFolderId:
      shNode.RemoveItem(parentFolderId)

    parentFolderId = None
    for ptIdx in reversed(range(len(self.pointLabels))):
      pointLabel = self.pointLabels[ptIdx]
      nodeItemId = shNode.GetItemByDataNode(pointLabel.markupsNode)
      parentFolderId = shNode.GetItemParent(nodeItemId)
      slicer.mrmlScene.RemoveNode(pointLabel.markupsNode)
    self.pointLabels = []
    if parentFolderId:
      shNode.RemoveItem(parentFolderId)

    outputModel = self.getOutputModelNode()
    if outputModel:
      slicer.mrmlScene.RemoveNode(outputModel)

  # def __repr__(self):
  #   return f"TagInfo: \n\t{self.pointInfo}\n\n" + \
  #          f"LabelInfo: \n\t{self.triangleInfo}\n\n" + \
  #          f"TagTriangles: \n\t{self.triangles}\n\n" + \
  #          f"TagPoints: \n\t{self.points}\n\n" + \
  #          f"TagEdges: \n\t{self.edges}\n\n" + \
  #          f"LabelData: \n\t{self.labelData}"

  def configurePointLocator(self, node):
    if node:
      self.locator = vtk.vtkKdTreePointLocator()
      self.locator.SetDataSet(node.GetPolyData())
      self.locator.BuildLocator()
    else:
      self.locator = None

  def getClosestVertexAndRadius(self, pos):
    assert self.locator is not None
    vertexIdx = self.locator.FindClosestPoint(pos)
    poly = self.locator.GetDataSet()
    radiusArray = poly.GetPointData().GetArray(SCALAR_RADIUS_NAME)
    return vertexIdx, radiusArray.GetValue(vertexIdx)

  def moveNodeToFolder(self, node, subfolderName=None):
    moveNodeToFolder(self.syntheticSkeletonNode, node, subfolderName)

  def setSyntheticSkeletonNode(self, node):
    if self.syntheticSkeletonNode == node: # no change
      return

    self.syntheticSkeletonNode = node

    if self.syntheticSkeletonNode:
      self.setParameterDefaults()

  def getSyntheticSkeletonNode(self):
    return self.syntheticSkeletonNode

  def setParameterDefaults(self):
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    if self.syntheticSkeletonNode.GetHideFromEditors():
      self.syntheticSkeletonNode.SetHideFromEditors(False)
      shNode.RequestOwnerPluginSearch(self.syntheticSkeletonNode)
      shNode.SetItemAttribute(shNode.GetItemByDataNode(self.syntheticSkeletonNode), "ModuleName", MODULE_NAME)

    if self.getInputModelNode() is not None and self.locator is None:
      self.configurePointLocator(self.getInputModelNode())

    if not self.syntheticSkeletonNode.GetParameter(PARAM_POINT_GLYPH_SIZE):
      self.syntheticSkeletonNode.SetParameter(PARAM_POINT_GLYPH_SIZE, str(PARAM_DEFAULTS[PARAM_POINT_GLYPH_SIZE]))

    self.updatePointLabels()
    self.updateTriangleLabels()
    self.updatePoints()
    self.updateTriangles()

  def setInputModelNode(self, modelNode):
    if not self.syntheticSkeletonNode:
      logging.error("setInputModelNode failed: invalid syntheticSkeletonNode")
      return

    self.configurePointLocator(modelNode)

    self.syntheticSkeletonNode.SetNodeReferenceID(PARAM_INPUT_MODEL, modelNode.GetID() if modelNode else None)

    if modelNode and not self.getOutputModelNode():
      outputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", f"{modelNode.GetName()}_syn_skeleton")
      self.setOutputModelNode(outputModel)

    from SyntheticSkeletonLib.CustomData import CustomInformationReader
    customInfo = CustomInformationReader(self)
    if customInfo.hasCustomData():
      customInfo.readCustomData()
      self.generateEdges()
      self.updateOutputMesh()

      for uniqueId, edge in self.edges.items():
        assert uniqueId == pairNumber(edge.ptId1, edge.ptId2)

  def getInputModelNode(self):
    return self.syntheticSkeletonNode.GetNodeReference(PARAM_INPUT_MODEL) if self.syntheticSkeletonNode else None

  def setOutputModelNode(self, modelNode):
    if not self.syntheticSkeletonNode:
      logging.error("setOutputModelNode failed: invalid syntheticSkeletonNode")
      return

    self.syntheticSkeletonNode.SetNodeReferenceID(PARAM_OUTPUT_MODEL, modelNode.GetID() if modelNode else None)
    if modelNode:
      self.moveNodeToFolder(modelNode)

  def setGlyphScale(self, size):
    self.syntheticSkeletonNode.SetParameter(PARAM_POINT_GLYPH_SIZE, str(size))
    for pointLabel in self.pointLabels:
      pointLabel.glyphScale = float(self.syntheticSkeletonNode.GetParameter(PARAM_POINT_GLYPH_SIZE))

  def getOutputModelNode(self):
    return self.syntheticSkeletonNode.GetNodeReference(PARAM_OUTPUT_MODEL) if self.syntheticSkeletonNode else None

  def addPointLabel(self, markupsNode):
    logging.debug(f"addPointLabel {markupsNode.GetName()}")
    pointLabel = PointLabel(markupsNode)
    self.pointLabels.append(pointLabel)
    self.syntheticSkeletonNode.SetNthNodeReferenceID(ATTR_POINT_LABELS, len(self.pointLabels), markupsNode.GetID())
    self.moveNodeToFolder(markupsNode, subfolderName=ATTR_POINT_LABELS)
    self.addMarkupNodesObserver(markupsNode)
    pointLabel.glyphScale = float(self.syntheticSkeletonNode.GetParameter(PARAM_POINT_GLYPH_SIZE))

  def removePointLabel(self, markupsNode):
    logging.debug(f"removePointLabel {markupsNode.GetName()}")
    pointLabel = self.findPointLabel(markupsNode)
    self.removeMarkupNodesObserver(markupsNode)

    for idx in range(markupsNode.GetNumberOfControlPoints()):
      point = self.findPointByMarkupsNode(markupsNode, markupsNode.GetNthControlPointID(idx))
      if point:
        point.markupsNode = None

    self.pointLabels.remove(pointLabel)
    self.removeInvalidPoints()

    self.generateEdges()
    self.updateOutputMesh()

  def updatePointLabels(self):
    logging.debug("updatePointLabels")
    numberOfReferences = self.syntheticSkeletonNode.GetNumberOfNodeReferences(ATTR_POINT_LABELS)
    for referenceIndex in range(numberOfReferences):
      markupsNode = self.syntheticSkeletonNode.GetNthNodeReference(ATTR_POINT_LABELS, referenceIndex)
      pointLabel = self.findPointLabel(markupsNode)
      if not pointLabel:
        pointLabel = PointLabel(markupsNode)
        self.pointLabels.append(pointLabel)
      self.addMarkupNodesObserver(markupsNode)
      pointLabel.glyphScale = float(self.syntheticSkeletonNode.GetParameter(PARAM_POINT_GLYPH_SIZE))

  def findPointLabel(self, markupsNode):
    for pointLabel in self.pointLabels:
      if pointLabel.markupsNode == markupsNode:
        return pointLabel
    return None

  def onMarkupsNodeModified(self, node, event):
    self.updateOutputMesh()

  def addMarkupNodesObserver(self, markupsNode):
    self.addObserver(markupsNode, markupsNode.PointPositionDefinedEvent, self.onPointAdded)
    self.addObserver(markupsNode, markupsNode.PointStartInteractionEvent, self.onPointInteractionStarted)
    self.addObserver(markupsNode, markupsNode.PointEndInteractionEvent, self.onPointInteractionEnded)
    self.addObserver(markupsNode, markupsNode.PointRemovedEvent, self.onPointRemoved)
    self.addObserver(markupsNode, vtk.vtkCommand.ModifiedEvent, self.onMarkupsNodeModified)

  def removeMarkupNodesObserver(self, markupsNode):
    self.removeObserver(markupsNode, markupsNode.PointPositionDefinedEvent, self.onPointAdded)
    self.removeObserver(markupsNode, markupsNode.PointStartInteractionEvent, self.onPointInteractionStarted)
    self.removeObserver(markupsNode, markupsNode.PointEndInteractionEvent, self.onPointInteractionEnded)
    self.removeObserver(markupsNode, markupsNode.PointRemovedEvent, self.onPointRemoved)
    self.removeObserver(markupsNode, vtk.vtkCommand.ModifiedEvent, self.onMarkupsNodeModified)

  def onPointAdded(self, caller, event):
    logging.debug("Point Added")
    pointIdx = caller.GetNumberOfControlPoints()-1
    self.addPoint(caller, pointIdx)

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointRemoved(self, caller, event, localPointIdx, callModified=True):
    logging.debug(f"onPointRemoved: {caller.GetID()}, idx: {localPointIdx}")
    self.removeInvalidPoints()

    if callModified:
      self.generateEdges()
      self.updateOutputMesh()

  def updatePoints(self):
    logging.debug("updatePoints")

    numberOfReferences = self.syntheticSkeletonNode.GetNumberOfNodeReferences(ATTR_POINTS)
    for referenceIndex in range(numberOfReferences):
      scriptedNode = self.syntheticSkeletonNode.GetNthNodeReference(ATTR_POINTS, referenceIndex)
      if not self.findPointByScriptedNode(scriptedNode):
        point = Point(scriptedNode)
        self.points.append(point)

  def findPointByScriptedNode(self, scriptedNode):
    for point in self.points:
      if point.scriptedNode == scriptedNode:
        return point
    return None

  def findPointByMarkupsNode(self, markupsNode, ptId):
    if type(markupsNode) is str:
      markupsNode = slicer.util.getNode(markupsNode)
    for point in self.points:
      if point.markupsNode is markupsNode and point.pointID == ptId:
        return point
    return None

  def addPoint(self, markupsNode, ptIdx):
    scriptedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode",
                                                      slicer.mrmlScene.GetUniqueNameByString(f"{MODULE_NAME}Point"))
    scriptedNode.SetAttribute("ModuleName", MODULE_NAME)
    scriptedNode.SetAttribute("Type", f"{MODULE_NAME}Point")
    scriptedNode.SetNodeReferenceID("MarkupsNode", markupsNode.GetID())
    scriptedNode.SetAttribute("PointID", markupsNode.GetNthControlPointID(ptIdx))

    point = Point(scriptedNode)
    self.points.append(point)
    self.syntheticSkeletonNode.SetNthNodeReferenceID(ATTR_POINTS, len(self.points), scriptedNode.GetID())
    self.updatePoint(markupsNode, ptIdx)

  def updatePoint(self, markupsNode, ptIdx):
    pos = markupsNode.GetNthControlPointPosition(ptIdx)
    # snapping
    if slicer.util.toBool(markupsNode.GetAttribute(ATTR_TO_SURFACE)):
      vertexIdx = self.locator.FindClosestPoint(pos)
      poly = self.locator.GetDataSet()
      markupsNode.SetNthControlPointPosition(ptIdx, poly.GetPoints().GetPoint(vertexIdx))
    self.updateOutputMesh()

  def removeInvalidPoints(self):
    # removes invalid points and all related triangles
    for point in reversed(self.points):
      if not point.isValid():
        for triangle in reversed(self.triangles):
          if any(p is point.scriptedNode for p in triangle.points):
            slicer.mrmlScene.RemoveNode(triangle.scriptedNode)
            self.triangles.remove(triangle)
        slicer.mrmlScene.RemoveNode(point.scriptedNode)
        self.points.remove(point)

  def onPointInteractionStarted(self, caller, event):
    self.addObserver(caller, caller.PointModifiedEvent, self.onPointModified)

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointModified(self, caller, event, pointIdx):
    pointIdx = caller.GetDisplayNode().GetActiveControlPoint()
    logging.debug(f"modified event {caller.GetID}, {pointIdx}")
    # self.syntheticSkeletonModel.updatePoint(caller, pointIdx)

  def onPointInteractionEnded(self, caller, event):
    self.removeObserver(caller, caller.PointModifiedEvent, self.onPointModified)
    pointIdx = caller.GetDisplayNode().GetActiveControlPoint()
    self.updatePoint(caller, pointIdx)

  def addTriangleLabel(self, scriptedNode):
    self.triangleLabels.append(TriangleLabel(scriptedNode))
    self.syntheticSkeletonNode.SetNthNodeReferenceID(ATTR_TRIANGLE_LABELS, len(self.pointLabels), scriptedNode.GetID())
    if scriptedNode.GetHideFromEditors():
      scriptedNode.SetHideFromEditors(False)
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      shNode.RequestOwnerPluginSearch(scriptedNode)
    self.moveNodeToFolder(scriptedNode, subfolderName=ATTR_TRIANGLE_LABELS)
    self.addObserver(scriptedNode, vtk.vtkCommand.ModifiedEvent, self.onTriangleLabelModified)

  def removeTriangleLabel(self, scriptedNode):
    self.removeObserver(scriptedNode, vtk.vtkCommand.ModifiedEvent, self.onTriangleLabelModified)
    triangleLabel = self.findTriangleLabel(scriptedNode)

    scriptedNodes = []
    for triIdx, tri in enumerate(self.triangles):
      if tri.triangleLabel is triangleLabel.scriptedNode:
        scriptedNodes.append(tri.scriptedNode)

    for sn in scriptedNodes:
      self.removeTriangleByScriptedNode(sn)

    self.triangleLabels.remove(triangleLabel)

    self.generateEdges()
    self.updateOutputMesh()

  def assignTriangleLabel(self, pos, triangleLabelNode: str):
    poly = self.getOutputModelNode().GetPolyData()

    for lblIdx, triLabel in enumerate(self.triangleLabels):
      if triLabel.scriptedNode == triangleLabelNode:
        for triIdx, tri in enumerate(self.triangles):
          p1 = self.findPointByScriptedNode(tri.p1)
          p2 = self.findPointByScriptedNode(tri.p2)
          p3 = self.findPointByScriptedNode(tri.p3)
          if poly.GetCell(triIdx).PointInTriangle(pos, p1.pos, p2.pos, p3.pos, 0.1):
            tri.triangleLabel = triLabel.scriptedNode
            self.updateOutputMesh()
            break
        break
    return "No valid triangle label found"

  def updateTriangleLabels(self):
    logging.debug("updateTriangleLabels")

    numberOfReferences = self.syntheticSkeletonNode.GetNumberOfNodeReferences(ATTR_TRIANGLE_LABELS)
    for referenceIndex in range(numberOfReferences):
      scriptedNode = self.syntheticSkeletonNode.GetNthNodeReference(ATTR_TRIANGLE_LABELS, referenceIndex)
      triangleLabel = self.findTriangleLabel(scriptedNode)
      if not triangleLabel:
        self.triangleLabels.append(TriangleLabel(scriptedNode))
        self.addObserver(scriptedNode, vtk.vtkCommand.ModifiedEvent, self.onTriangleLabelModified)

  def findTriangleLabel(self, scriptedNode):
    for triangleLabel in self.triangleLabels:
      if triangleLabel.scriptedNode == scriptedNode:
        return triangleLabel
    return None

  def onTriangleLabelModified(self, caller, event):
    print("onTriangleLabelModified")
    self.updateOutputMesh()

  def updateTriangles(self):
    logging.debug("updateTriangles")

    numberOfReferences = self.syntheticSkeletonNode.GetNumberOfNodeReferences(ATTR_TRIANGLES)
    for referenceIndex in range(numberOfReferences):
      scriptedNode = self.syntheticSkeletonNode.GetNthNodeReference(ATTR_TRIANGLES, referenceIndex)
      if not self.findTriangleByScriptedNode(scriptedNode):
        tri = Triangle(scriptedNode)
        self.triangles.append(tri)

  def findTriangleByScriptedNode(self, scriptedNode):
    for tri in self.triangles:
      if tri.scriptedNode == scriptedNode:
        return tri
    return None

  def attemptToAddTriangle(self, selectedPoints, selectedTriangleLabel):
    for triLabel in self.triangleLabels:
      if triLabel.scriptedNode is selectedTriangleLabel:
        return self.addTriangle(selectedPoints, triLabel)
    raise ValueError("No valid triangle label found")

  def addTriangle(self, selectedPoints, triangleLabel):
    points = [self.findPointByMarkupsNode(mn, ptId) for mn, ptId in selectedPoints]
    assert all(p is not None for p in points)
    selTriPtIds = [self.points.index(p) for p in points]
    logging.debug(f"ID {selTriPtIds}")

    # CurvePointOrder
    logging.debug(selTriPtIds)
    triPtIds = self.checkNormal(selTriPtIds.copy())
    logging.debug(triPtIds)
    m = self.checkEdgeConstraints(triPtIds)
    if m:
      raise ValueError(m)

    scriptedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode",
                                                      slicer.mrmlScene.GetUniqueNameByString(f"{MODULE_NAME}Triangle"))
    scriptedNode.SetAttribute("ModuleName", MODULE_NAME)
    scriptedNode.SetAttribute("Type", f"{MODULE_NAME}Triangle")

    tri = Triangle(scriptedNode)
    tri.p1 = self.points[triPtIds[0]].scriptedNode
    tri.p2 = self.points[triPtIds[1]].scriptedNode
    tri.p3 = self.points[triPtIds[2]].scriptedNode
    tri.triangleLabel = triangleLabel.scriptedNode
    self.syntheticSkeletonNode.SetNthNodeReferenceID(ATTR_TRIANGLES, len(self.triangles), scriptedNode.GetID())

    self.triangles.append(tri)

    self.generateEdges()
    self.updateOutputMesh()

    nextTriPtIds = self.getNextTriPt(tri)
    logging.debug(f"after {triPtIds}")
    logging.debug(f"Next PT ids {nextTriPtIds}")
    return [selTriPtIds.index(ptId) for ptId in nextTriPtIds]

  def removeTriangleByScriptedNode(self, scriptedNode):
    for triIdx, tri in enumerate(self.triangles):
      if tri.scriptedNode is scriptedNode:
        tri.deleteLater()
        self.triangles.remove(tri)
        return

  def removeTriangle(self, pos):
    poly = self.getOutputModelNode().GetPolyData()

    for triIdx, tri in enumerate(self.triangles):
      p1 = self.findPointByScriptedNode(tri.p1)
      p2 = self.findPointByScriptedNode(tri.p2)
      p3 = self.findPointByScriptedNode(tri.p3)
      if poly.GetCell(triIdx).PointInTriangle(pos, p1.pos, p2.pos, p3.pos, 0.1):
        self.removeTriangleByScriptedNode(tri.scriptedNode)
        break
    self.generateEdges()
    self.updateOutputMesh()

  def triPtIds(self, tri):
    points = [self.findPointByScriptedNode(p) for p in tri.points]
    return [self.points.index(p) for p in points]

  def getNextTriPt(self, tri):
    triPtIds = self.triPtIds(tri)
    if self.isValidEdge(triPtIds[1], triPtIds[2]):
      return [triPtIds[1], triPtIds[2]]
    elif self.isValidEdge(triPtIds[0], triPtIds[1]):
      return [triPtIds[0], triPtIds[1]]
    elif self.isValidEdge(triPtIds[0], triPtIds[2]):
      return [triPtIds[0], triPtIds[2]]
    else:
      return []

  def flipTriangleNormal(self, pos):
    poly = self.getOutputModelNode().GetPolyData()

    for triIdx, tri in enumerate(self.triangles):
      p1 = self.findPointByScriptedNode(tri.p1)
      p2 = self.findPointByScriptedNode(tri.p2)
      p3 = self.findPointByScriptedNode(tri.p3)
      if poly.GetCell(triIdx).PointInTriangle(pos, p1.pos, p2.pos, p3.pos, 0.1):
        # flip the 2nd and 3rd vertices
        tempPos = tri.p2
        tri.p2 = tri.p3
        tri.p3 = tempPos
        break
    self.updateOutputMesh()

  def generateEdges(self):
    self.edges = OrderedDict()
    for tri in self.triangles:
      self.checkEdgeConstraints(self.triPtIds(tri))

  def checkNormal(self, triPtIds):
    idx1, idx2, idx3 = triPtIds

    normalGenerator = vtk.vtkPolyDataNormals()
    surface = self.getInputModelNode()
    normalGenerator.SetInputData(surface.GetPolyData())
    normalGenerator.Update()
    normalPolyData = normalGenerator.GetOutput()
    normalDataFloat = normalPolyData.GetPointData().GetArray("Normals")

    points = self.points

    if normalDataFloat:
      seq1, _ = self.getClosestVertexAndRadius(points[idx1].pos)
      normal1 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(seq1, normal1)
      seq2, _ = self.getClosestVertexAndRadius(points[idx2].pos)
      normal2 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(seq2, normal2)
      seq3, _ = self.getClosestVertexAndRadius(points[idx3].pos)
      normal3 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(seq3, normal3)

      import numpy as np

      normalAverage = np.array([
        (normal1[0] + normal2[0] + normal3[0]) / 3.0,
        (normal1[1] + normal2[1] + normal3[1]) / 3.0,
        (normal1[2] + normal2[2] + normal3[2]) / 3.0
      ])

      d1 = np.array([
        points[idx2].pos[0] - points[idx1].pos[0],
        points[idx2].pos[1] - points[idx1].pos[1],
        points[idx2].pos[2] - points[idx1].pos[2]
      ])

      d2 = np.array([
        points[idx3].pos[0] - points[idx2].pos[0],
        points[idx3].pos[1] - points[idx2].pos[1],
        points[idx3].pos[2] - points[idx2].pos[2]
      ])

      result = [0.0, 0.0, 0.0]
      vtk.vtkMath.Cross(d1, d2, result)
      vtk.vtkMath.Normalize(result)
      vtk.vtkMath.Normalize(normalAverage)

      cos = vtk.vtkMath.Dot(result, normalAverage)

      if cos < 0: # need to swap
        tempid = triPtIds[1]
        triPtIds[1] = triPtIds[2]
        triPtIds[2] = tempid

    return triPtIds

  def checkEdgeConstraints(self, triPtIds):
    edge1 = self.getOrCreateEdge(triPtIds[0], triPtIds[1])
    if edge1.numEdge >= edge1.constrain:
      return f"Edge number 1 already has {edge1.numEdge} connection(s) and can only have {edge1.constrain} connection(s) maximum."
    edge2 = self.getOrCreateEdge(triPtIds[1], triPtIds[2])
    if edge2.numEdge >= edge2.constrain:
      return f"Edge number 2 already has {edge2.numEdge} connection(s) and can only have {edge2.constrain} connection(s) maximum."
    edge3 = self.getOrCreateEdge(triPtIds[2], triPtIds[0])
    if edge3.numEdge >= edge3.constrain:
      return f"Edge number 3 already has {edge3.numEdge} connection(s) and can only have {edge3.constrain} connection(s) maximum."

    edge1.increaseNumEdges()
    edge2.increaseNumEdges()
    edge3.increaseNumEdges()

    return ""

  def isValidEdge(self, ptId1, ptId2):
    edge = self.getEdge(ptId1, ptId2)
    if not edge:
      cons = getEdgeConstraint(self.points[ptId1], self.points[ptId2])
      edge = Edge(
        ptId1=ptId1,
        ptId2=ptId2,
        seq=0,
        numEdge=0,
        constrain=cons
      )

    if edge.numEdge >= edge.constrain:
      return False
    return True

  def getEdge(self, ptId1, ptId2):
    edgeId12 = pairNumber(ptId1, ptId2)
    if edgeId12 in self.edges.keys():
      return self.edges[edgeId12]
    edgeId21 = pairNumber(ptId2, ptId1)
    if edgeId21 in self.edges.keys():
      return self.edges[edgeId21]
    return None

  def getOrCreateEdge(self, ptId1, ptId2):
    edge = self.getEdge(ptId1, ptId2)
    if not edge:
      edgeId12 = pairNumber(ptId1, ptId2)
      cons = getEdgeConstraint(self.points[ptId1], self.points[ptId2])
      edge = Edge(
        ptId1=ptId1,
        ptId2=ptId2,
        seq=0,
        numEdge=0,
        constrain=cons
      )
      self.edges[edgeId12] = edge
    return edge

  def updateOutputMesh(self):
    import  vtk

    meshPoly = vtk.vtkPolyData()
    meshPoints = vtk.vtkPoints()
    meshPoly.SetPoints(meshPoints)

    for pt in self.points:
      meshPoints.InsertNextPoint(pt.pos)

    radiusArray = vtk.vtkFloatArray()
    radiusArray.SetName(SCALAR_RADIUS_NAME)
    for pt in self.points:
      _, radius = self.getClosestVertexAndRadius(pt.pos)
      radiusArray.InsertNextValue(radius)
    meshPoly.GetPointData().AddArray(radiusArray)

    labelArray = vtk.vtkFloatArray()
    labelArray.SetName(SCALAR_POINT_ANATOMICAL_INDEX_NAME)
    for pt in self.points:
      labelArray.InsertNextValue(pt.anatomicalIndex)
    meshPoly.GetPointData().AddArray(labelArray)

    colorsArray = vtk.vtkUnsignedCharArray()
    colorsArray.SetNumberOfComponents(3)
    colorsArray.SetName(SCALAR_TRIANGLE_COLOR_NAME)

    fltArray8 = vtk.vtkFloatArray()
    fltArray8.SetName(SCALAR_TRIANGLE_ANATOMICAL_INDEX_NAME)

    triangles = vtk.vtkCellArray()
    for tri in self.triangles:
      triPtIds = self.triPtIds(tri)
      triangle = vtk.vtkTriangle()
      triangle.GetPointIds().SetId(0, triPtIds[0])
      triangle.GetPointIds().SetId(1, triPtIds[1])
      triangle.GetPointIds().SetId(2, triPtIds[2])
      triangles.InsertNextCell(triangle)

      triangleLabel = self.findTriangleLabel(tri.triangleLabel)
      color = qt.QColor(triangleLabel.color)
      colorsArray.InsertNextTuple3(color.red(), color.green(), color.blue())

      fltArray8.InsertNextValue(self.triangleLabels.index(triangleLabel) + 1)

    meshPoly.GetCellData().AddArray(fltArray8)
    meshPoly.GetCellData().SetScalars(colorsArray)
    meshPoly.SetPoints(meshPoints)
    meshPoly.SetPolys(triangles)

    self.getOutputModelNode().SetAndObservePolyData(meshPoly)


class PointLabel(object):

  @property
  def name(self):
    return self.markupsNode.GetName()

  @property
  def anatomicalIndex(self):
    return int(self.markupsNode.GetAttribute("AnatomicalIndex"))

  @property
  def typeIndex(self):
    # 1 = Branch point  2 = Free Edge point 3 = Interior point  4 = others
    return int(self.markupsNode.GetAttribute("TypeIndex"))

  @property
  def glyphScale(self):
    dNode = self.markupsNode.GetDisplayNode()
    return dNode.GetGlyphScale()

  @glyphScale.setter
  def glyphScale(self, size):
    dNode = self.markupsNode.GetDisplayNode()
    dNode.SetGlyphScale(float(size))

  def __init__(self, markupsNode):
    logging.debug(f"created PointLabel for markupsNode {markupsNode.GetID()}")
    self.markupsNode = markupsNode
    self._configueDisplaySettings()

  def _configueDisplaySettings(self):
    node = self.markupsNode
    dnode = node.GetDisplayNode()
    if not dnode:
      node.CreateDefaultDisplayNodes()
      dnode = node.GetDisplayNode()
    dnode.SetTextScale(0)
    dnode.SetColor(DEFAULT_POINT_COLOR)
    dnode.SetActiveColor(DEFAULT_POINT_COLOR)
    dnode.SetPointLabelsVisibility(False)
    dnode.SetPropertiesLabelVisibility(False)

    node.SetAttribute(ATTR_TYPE_INDEX,
                      str(node.GetAttribute(ATTR_TYPE_INDEX) if node.GetAttribute(ATTR_TYPE_INDEX) else -1))
    snapToSurface = node.GetAttribute(ATTR_TO_SURFACE)
    node.SetAttribute(ATTR_TO_SURFACE, str(snapToSurface) if snapToSurface else str(True))


class TriangleLabel(object):

  @property
  def color(self):
    return self.scriptedNode.GetAttribute(ATTR_COLOR)

  @property
  def name(self):
    return self.scriptedNode.GetName()

  def __init__(self, scriptedNode):
    logging.debug(f"created TriangleLabel for scriptedNode {scriptedNode.GetID()}")
    self.scriptedNode = scriptedNode


class Triangle:

  @property
  def points(self):
    return [self.p1, self.p2, self.p3]

  @property
  def p1(self):
    return self.scriptedNode.GetNthNodeReference(ATTR_POINTS, 0)

  @p1.setter
  def p1(self, node):
    return self.scriptedNode.SetNthNodeReferenceID(ATTR_POINTS, 0, node.GetID())

  @property
  def p2(self):
    return self.scriptedNode.GetNthNodeReference(ATTR_POINTS, 1)

  @p2.setter
  def p2(self, node):
    return self.scriptedNode.SetNthNodeReferenceID(ATTR_POINTS, 1, node.GetID())

  @property
  def p3(self):
    return self.scriptedNode.GetNthNodeReference(ATTR_POINTS, 2)

  @p3.setter
  def p3(self, node):
    return self.scriptedNode.SetNthNodeReferenceID(ATTR_POINTS, 2, node.GetID())

  @property
  def triangleLabel(self):
    return self.scriptedNode.GetNodeReference(ATTR_TRIANGLE_LABELS)

  @triangleLabel.setter
  def triangleLabel(self, node):
    self.scriptedNode.SetNodeReferenceID(ATTR_TRIANGLE_LABELS, node.GetID() if node else "")

  def __init__(self, scriptedNode):
    self.scriptedNode = scriptedNode

  def deleteLater(self):
    qt.QTimer.singleShot(500, lambda: slicer.mrmlScene.RemoveNode(self.scriptedNode))


class Point:
  """ use ID as identifier """

  @property
  def markupsNode(self):
    return self.scriptedNode.GetNodeReference("MarkupsNode")

  @markupsNode.setter
  def markupsNode(self, node):
    self.scriptedNode.SetNodeReferenceID("MarkupsNode", node.GetID() if node is not None else "")

  @property
  def pointIndex(self):
    return self.markupsNode.GetNthControlPointIndexByID(self.pointID)

  @property
  def pointID(self):
    return self.scriptedNode.GetAttribute("PointID")

  @property
  def pos(self):
    return self.markupsNode.GetNthControlPointPosition(self.pointIndex)

  @property
  def anatomicalIndex(self):
    return int(self.markupsNode.GetAttribute(ATTR_ANATOMICAL_INDEX))

  @property
  def typeIndex(self):
    return int(self.markupsNode.GetAttribute(ATTR_TYPE_INDEX))

  def __init__(self, scriptedNode):
    self.scriptedNode = scriptedNode

  def isValid(self):
    return not self.markupsNode is None and self.pointIndex != -1


@dataclass
class Edge:
  ptId1: int
  ptId2: int
  constrain: int
  numEdge: int
  seq: int

  def increaseNumEdges(self):
    self.numEdge += 1

  @property
  def edgPtIds(self):
    return [self.ptId1, self.ptId2]
