import numpy as np
import logging
from functools import wraps
from .Constants import *
import slicer


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