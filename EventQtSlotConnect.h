#ifndef EventQtSlotConnect_H
#define EventQtSlotConnect_H

#include <QtCore/QtGlobal>
#include "ui_EventQtSlotConnect.h"
#include "VoronoiSkeletonTool.h"
#include "AddTagDialog.h"
#include "AddLabelDialog.h"
#include "MouseInteractor.h"
#include "ToggleTriLabel.h"
#include "importNiftiiWindow.h"

#include "itkDiscreteGaussianImageFilter.h"
#include "itkSmoothingRecursiveGaussianImageFilter.h"
#include "itkOrientedRASImage.h"
#include "itkIOCommon.h"
#include "itkImageFileReader.h"
#include "itkMetaDataDictionary.h"
#include "itkMetaDataObject.h"
#include "itkGDCMSeriesFileNames.h"
#include "itkGDCMImageIO.h"
#include "itkImageSeriesReader.h"
#include "itkImageFileWriter.h"
#include "itkBinaryThresholdImageFilter.h"
#include "itkVTKImageExport.h"
#include "vtkImageImport.h"
#include "vtkMarchingCubes.h"
#include "vtkTransformPolyDataFilter.h"
#include "itk_to_nifti_xform.h"
#include <vtkPolyDataWriter.h>

#include <QMainWindow>
#include <vtkSmartPointer.h>
#include <QFutureWatcher>
#if QT_VERSION >= 0x050000
    #include <QtWidgets>
    #include <QtConcurrent/QtConcurrent>
#else
    #include <QtGui>
#endif
#include <vtkPolyData.h>
#include <vtkStringArray.h>

QT_BEGIN_NAMESPACE
class QAction;
class QActionGroup;
class QLabel;
class QMenu;
QT_END_NAMESPACE

class vtkEventQtSlotConnect;

class EventQtSlotConnect : public QMainWindow, private Ui::EventQtSlotConnect
{
    Q_OBJECT
public:
	EventQtSlotConnect();
	~EventQtSlotConnect();
	void createActions();
	void createMenus();
	void readVTK(std::string filename);
	itk::SmartPointer<itk::OrientedRASImage<double, 3>> threshold(itk::SmartPointer<itk::OrientedRASImage<double, 3>> input, double u1, double u2, double v1, double v2);
	itk::SmartPointer<itk::OrientedRASImage<double, 3>> smooth(itk::SmartPointer<itk::OrientedRASImage<double, 3>> input, const char* sigma);
	void writeNiftii(itk::SmartPointer<itk::OrientedRASImage<double, 3>> input, const char *output);
	void importNIFTI(std::vector<std::string> filenames, bool checked, std::string sigma = "2", std::vector<std::string> th1Param = {"", "", "", ""}, std::vector<std::string> th2Param = {"", "", "", ""});
	void vtklevelset(const char *inputNii, const char *outputVtk, std::string threshold);
	QComboBox* getTagComboBox();
	void readCustomData(vtkPolyData *polydata);
	void readCustomDataTri(vtkFloatArray* triDBL);
	void readCustomDataEdge(vtkFloatArray* edgeDBL);
	void readCustomDataPoints(vtkFloatArray* ptsDBL);
	void readCustomDataTag(vtkFloatArray* tagDBL, vtkStringArray* tagStr);
	void readCustomDataLabel(vtkFloatArray* labelDBL);

	void saveVTKFile(QString fileName);
	void saveParaViewFile(QString fileName);
	void saveCmrepFile(QString fileName);

	//void Decimate();

    QColor colorBckgnd;

public slots:
	void slot_finished();
	void slot_skelStateChange(int);
	void slot_meshStateChange(int);
	void slot_addTag();
	void slot_delTag();
	void slot_editTag();
    void slot_addLabel();
	void slot_delLabel();
	void slot_editLabel();
	void slot_comboxChanged(int);

    /*void slot_undo();
    void slot_redo();*/

	void slot_gridTypeChanged(int);
	void slot_solverTypeChanged(int);
	void slot_consRadiusCheck(int);
	
	void slot_toggleTriLabel();

	void browsePath();
	void slot_open();
	void slot_save();
	void slot_import();

//	void slot_targetReductSilder(int);
//	void slot_targetReductEditor(QString);
//	void slot_featureAngleSlider(int);
//	void slot_feartureAngleEditor(QString);
//	void slot_decimateButton();

	void slot_tagSizeSlider(int);

	void slot_addPoint();
	void slot_deletePoint();
	void slot_createTri();
	void slot_deleteTri();
	void slot_flipNormal();
	void slot_view();
    void slot_changePtLabel();
	void slot_changeTriLabel();
	void slot_movePoint();

	void slot_updateOperation(int);

	void slot_updateProgressBar();

	void slot_skelTransparentChanged(int);
	void slot_meshTransparentChanged(int);

	void slot_trilabelChanged(int);

    void slot_setColor();

	void executeCmrepVskel();	

private:
	unsigned int VDim;

	void loadSettings();
	void saveSettings();
	void setToolButton(int flag);
	void iniTriLabel();

	QString settingsFile;

	vtkSmartPointer<vtkEventQtSlotConnect> Connections;
	QFutureWatcher<void> FutureWatcher;
	VoronoiSkeletonTool v;

	QMenu *fileMenu;
	QAction *openAct;
	QAction *saveAct;
	QAction *importAct;

	std::string VTKfilename;  
	vtkPolyData* polyObject;

	double targetReduction;
	double featureAngle;

	vtkSmartPointer<MouseInteractor> mouseInteractor;

	int progressSignalCount;

	std::vector<QColor> triLabelColors;
	std::vector<int> hideTriLabel;
	typedef itk::OrientedRASImage<double, 3> ImageType;
	typedef itk::SmartPointer<ImageType> ImagePointer;
};

#endif
