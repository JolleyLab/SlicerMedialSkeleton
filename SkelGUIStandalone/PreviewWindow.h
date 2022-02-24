#ifndef PREVIEWWINDOW_H
#define PREVIEWWINDOW_H


#include <vtkActor.h>
#include <vtkFloatArray.h>
#include <vtkLookupTable.h>
#include <vtkPointData.h>
#include <vtkPolyData.h>
#include <vtkPolyDataMapper.h>
#include <vtkRenderer.h>
#include <vtkRenderWindow.h>
#include <vtkRendererCollection.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkScalarBarActor.h>
#include <vtkSmartPointer.h>
#include <vtkSphereSource.h>
#include <vtkPolyDataReader.h>
#include <vtkTriangle.h>
#include <vtkProperty.h>
#include "global.h"
#include <vtkAppendPolyData.h>
#include <vtkCleanPolyData.h>
#include <vtkLoopSubdivisionFilter.h>
#include <vtkColorTransferFunction.h>
#include <vtkTextProperty.h>

#include "ui_PreviewWindow.h"
#include <QWidget>

QT_BEGIN_NAMESPACE
//class QCheckBox;
class QDialogButtonBox;
class QGroupBox;
class QLabel;
//class QLineEdit;
class QPushButton;
//class QRadioButton;
//class QComboBox;
class QVTKWidget;
QT_END_NAMESPACE

//! [0]
class PreviewWindow : public QWidget, private Ui::PreviewWindow
{
    Q_OBJECT

public:
    PreviewWindow(std::string fileName, std::vector<double> radius, vtkSmartPointer<vtkPolyData> triangulateMesh, QWidget *parent = 0);
	vtkPolyData *ReadVTKData(std::string fileName);
	void SegmentationMesh(vtkPolyData *mesh);
	void SetScalarsData(vtkSmartPointer<vtkPolyData> triangulateMesh, std::vector<double> radius);
	void getColorCorrespondingTovalue(double val,double &r, double &g, double &b, double min, double max, double range);

private:
	std::vector<double> radius;
	vtkPolyData *mesh;

public slots:
	void showSegmentation(int state);
	void segmentationOpacity(int opacity);
};
//! [0]

#endif // PREVIEWWINDOW_H
