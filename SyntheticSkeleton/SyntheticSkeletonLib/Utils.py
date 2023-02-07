import numpy as np
import logging
from functools import wraps
from SyntheticSkeletonLib.Constants import *
import slicer


def loadModel(filepath, coordinateSystem):
  properties = {
    'coordinateSystem': slicer.vtkMRMLModelStorageNode.GetCoordinateSystemFromString(coordinateSystem)
  }
  slicer.util.loadNodeFromFile(filepath, 'ModelFile', properties)


def readBinaryImageAndConvertToModel(path):
  segNode = None
  try:
    segNode = slicer.util.loadSegmentation(path)
    segmentationsLogic = slicer.modules.segmentations.logic()
    segmentationsLogic.ExportVisibleSegmentsToModels(segNode, 0)
  except RuntimeError as exc:
    slicer.util.errorDisplay(exc, "RuntimeError")
  finally:
    if segNode:
      slicer.mrmlScene.RemoveNode(segNode)


def writePolydata(polydata, outputFilePath, useRAS=True):
  modelsLogic = slicer.modules.models.logic()
  modelNode = modelsLogic.AddModel(polydata)
  saveModel(modelNode, outputFilePath, useRAS)
  slicer.mrmlScene.RemoveNode(modelNode)


def saveModel(modelNode, outputFilePath, useRAS=True):
  storageNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelStorageNode")
  storageNode.SetUseCompression(False)
  storageNode.SetFileName(outputFilePath)
  storageNode.SetCoordinateSystem(slicer.vtkMRMLStorageNode.CoordinateSystemRAS if useRAS else
                                  slicer.vtkMRMLStorageNode.CoordinateSystemLPS)

  if not storageNode.WriteData(modelNode):
    raise RuntimeError("Failed to save node: " + modelNode.GetName())
  slicer.mrmlScene.RemoveNode(storageNode)


def moveNodeToFolder(parent, node, subfolderName=None):
  shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
  valveNodeItemId = shNode.GetItemByDataNode(parent)
  if subfolderName:
    folderItemId = shNode.GetItemChildWithName(valveNodeItemId, subfolderName)
    if not folderItemId:
      folderItemId = shNode.CreateFolderItem(valveNodeItemId, subfolderName)
  else:
    folderItemId = valveNodeItemId
  shNode.SetItemParent(shNode.GetItemByDataNode(node), folderItemId)


def deleteFolderItem(parent, subfolderName):
  shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
  valveNodeItemId = shNode.GetItemByDataNode(parent)
  folderItemId = shNode.GetItemChildWithName(valveNodeItemId, subfolderName)
  if folderItemId:
    shNode.RemoveItem(folderItemId)


def isTriangleLabel(node):
  return isinstance(node, slicer.vtkMRMLScriptedModuleNode) and node.GetAttribute('ModuleName') == MODULE_NAME \
         and node.GetAttribute('Type') == "TriangleLabel"


def isPointLabel(node):
  return isinstance(node, slicer.vtkMRMLMarkupsFiducialNode) and node.GetAttribute('ModuleName') == MODULE_NAME


def hex2rgb(hex):
  from PIL import ImageColor
  return np.array(ImageColor.getcolor(hex, "RGB")) / 255.0


def blockedUpdate(widget, node):
  wasBlocked = widget.blockSignals(True)
  widget.setCurrentNode(node)
  widget.blockSignals(wasBlocked)


def preCheckConstraints(points):
  types = [TAG_TYPES[int(slicer.util.getNode(mn).GetAttribute(ATTR_TYPE_INDEX))] for mn, _ in points]

  if len(types) == 2 and all(t == EDGE_POINT for t in types):
    return checkEdgePoints(points, 0, 1)

  if len(types) == 3:
    if all(t == EDGE_POINT for t in types):
      return f"Cannot use three points of type '{EDGE_POINT}' to create triangle"
    else: # not all are edge points
      indices = [i for i, x in enumerate(types) if x == EDGE_POINT]
      if len(indices) == 2:
        return checkEdgePoints(points, indices[0], indices[1])
  return ""


def checkEdgePoints(points, ptIdx1, ptIdx2):
  m = ""
  if points[ptIdx1][0] != points[ptIdx2][0]: # different point lists
    return f"Cannot use edge points from different lists"

  node = slicer.util.getNode(points[ptIdx1][0])
  sortedIndices = getSortedPointIndices(slicer.util.arrayFromMarkupsControlPoints(node))
  for ix, idx in enumerate(sortedIndices):
    node.SetNthMarkupLabel(idx, f"{ix}")
  mn1 = slicer.util.getNode(points[ptIdx1][0])
  mn2 = slicer.util.getNode(points[ptIdx2][0])
  pt1Idx = sortedIndices.index(mn1.GetNthControlPointIndexByID(points[ptIdx1][1]))
  pt2Idx = sortedIndices.index(mn2.GetNthControlPointIndexByID(points[ptIdx2][1]))
  nControlPoints = node.GetNumberOfControlPoints()
  # taking care of case if first and last idx was selected (which are neighbors)
  if not sorted([pt1Idx, pt2Idx]) == [0, nControlPoints - 1] and abs(pt1Idx - pt2Idx) != 1:
    m = "Violation: Only directly neighboring edge points can be connected."
  return m


def getEdgeConstraint(point1, point2) -> int:
  """ returning number of allowed edges for the given tag points

  :param point1: TagPoint
  :param point2: TagPoint
  :return:
  """
  type1 = point1.typeIndex
  type2 = point2.typeIndex

  # 1 = Branch point  2 = Free Edge point 3 = Interior point  4 = others
  if type1 == 2 and type2 == 2:  # edge points
    return 1
  elif type1 == 3 and type2 == 3:  # interior points
    return 2
  elif (type1 == 1 and type2 == 2) or (type1 == 2 and type2 == 1):  # branch point and edge point
    return 2
  elif (type1 == 1 and type2 == 3) or (type1 == 3 and type2 == 1):  # branch point and interior point
    return 2
  elif (type1 == 2 and type2 == 3) or (type1 == 3 and type2 == 2):  # edge point and interior point
    return 2
  elif type1 == 1 and type2 == 1:  # branch points
    return 3
  raise ValueError("Cannot check edge constraints. Please make sure that all point labels have a point type assigned.")


def whenDoneCall(functionToCall):
  """ This decorator calls functionToCall after the decorated function is done.

  Args:
    functionToCall(function): function to be called after the decorated function
  """
  def decorator(func):
    @wraps(func)
    def f(*args, **kwargs):
      logging.debug("calling {} after {}".format(functionToCall.__name__, func.__name__))
      func(*args, **kwargs)
      functionToCall(args[0])
    return f
  return decorator


def pairNumber(a: int, b: int) -> int:
  """ Cantor pairing function """
  a1 = min(a, b)
  b1 = max(a, b)
  return int((a1 + b1) * (a1 + b1 + 1) / 2.0 + b1)


# source: http://stackoverflow.com/questions/12299540/plane-fitting-to-4-or-more-xyz-points
def planeFit(points):
  """
  p, n = planeFit(points)

  Given an array, points, of shape (d,...)
  representing points in d-dimensional space,
  fit an d-dimensional plane to the points.
  Return a point, p, on the plane (the point-cloud centroid),
  and the normal, n.
  """
  from numpy.linalg import svd
  points = np.reshape(points, (np.shape(points)[0], -1)) # Collapse trialing dimensions
  assert points.shape[0] <= points.shape[1], "There are only {} points in {} dimensions.".format(points.shape[1],
                                                                                                 points.shape[0])
  ctr = points.mean(axis=1)
  x = points - ctr[:,np.newaxis]
  M = np.dot(x, x.T) # Could also use np.cov(x) here.
  return ctr, svd(M)[0][:,-1]


def getBasePointToLineAngle(planeNormal, basePoint, lineOrigin, lineTip):
  import numpy as np
  def getUnitVector(lineOrigin, lineTip):
    vector = lineTip - lineOrigin
    return vector / np.linalg.norm(vector)
  planeNormal = planeNormal / np.linalg.norm(planeNormal)
  v1 = getUnitVector(lineOrigin, lineTip)
  v2 = getUnitVector(lineOrigin, basePoint)
  dot = np.dot(v1, v2)
  det = np.dot(planeNormal, np.cross(v1, v2))
  angle_deg = np.rad2deg(np.arctan2(det, dot))
  angle_deg = np.abs(angle_deg) if angle_deg < 0 else 360.0 - angle_deg
  return angle_deg


def getSortedPointIndices(rawPointsArray):
  import numpy as np
  planePosition, planeNormal = planeFit(rawPointsArray.T)
  base = rawPointsArray[0]
  angles = []
  for pos in rawPointsArray:
    angles.append(getBasePointToLineAngle(planeNormal, base, planePosition, pos))
  return list(np.argsort(angles))


def reload(packageName, submoduleNames):
  import imp
  f, filename, description = imp.find_module(packageName)
  package = imp.load_module(packageName, f, filename, description)
  for submoduleName in submoduleNames:
    f, filename, description = imp.find_module(submoduleName, package.__path__)
    try:
      imp.load_module(packageName + '.' + submoduleName, f, filename, description)
    finally:
      f.close()


def getOrCreateModelNode(name):
  try:
    node = slicer.util.getNode(name)
  except slicer.util.MRMLNodeNotFoundException:
    node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', name)
  return node


def deleteNode(name):
  try:
    node = slicer.util.getNode(name)
    if node:
      slicer.mrmlScene.RemoveNode(node)
  except slicer.util.MRMLNodeNotFoundException:
    pass


def configureDisplayNode(node, array):
  dispNode = node.GetDisplayNode()
  if not dispNode:
    node.CreateDefaultDisplayNodes()
    dispNode = node.GetDisplayNode()

  if array is None:
    dispNode.SetScalarVisibility(False)
    return

  arrayLocation = getArrayLocation(node.GetPolyData(), array)
  if arrayLocation == -1:
    print("Couldn't find array in polydata")
    return

  scalarName = array.GetName()
  dispNode.SetActiveScalar(scalarName, arrayLocation)
  dispNode.SetScalarVisibility(True)
  if scalarName == SCALAR_TRIANGLE_COLOR_NAME:
    dispNode.EdgeVisibilityOn()
    dispNode.SetScalarRangeFlagFromString("UseDirectMapping")
  elif scalarName in [SCALAR_RADIUS_NAME, SCALAR_TRIANGLE_COLOR_NAME, SCALAR_POINT_ANATOMICAL_INDEX_NAME]:
    dispNode.EdgeVisibilityOff()
    dispNode.SetAndObserveColorNodeID(SCALAR_COLOR_NODE_IDS[scalarName])
    if scalarName == SCALAR_RADIUS_NAME:
      dispNode.SetScalarRangeFlagFromString("UseData")
    else:
      dispNode.SetScalarRangeFlagFromString("UseColorNode")


def getArrayLocation(polydata, array):
  for locationIdx, locationData in enumerate([polydata.GetPointData(), polydata.GetCellData()]):
    for idx in range(locationData.GetNumberOfArrays()):
      if locationData.GetArray(idx) is array:
        return locationIdx
  return -1


def getArrayByName(polydata, arrayName):
  for locationData in [polydata.GetPointData(), polydata.GetCellData()]:
    for idx in range(locationData.GetNumberOfArrays()):
      arr = locationData.GetArray(idx)
      if arr.GetName() == arrayName:
        return arr
  return None


def confirmOrIgnoreDialog(message, title='Violation'):
  import qt
  box = qt.QMessageBox(qt.QMessageBox.Question, title, message)
  box.setStandardButtons(qt.QMessageBox.Ok | qt.QMessageBox.Ignore)
  return box.exec_() == qt.QMessageBox.Ok


def setAllControlPointsLocked(markupsNode, locked):
  for idx in range(markupsNode.GetNumberOfControlPoints()):
    markupsNode.SetNthControlPointLocked(idx, locked)