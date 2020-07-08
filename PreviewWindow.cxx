#include <QtCore/QtGlobal>

#if QT_VERSION >= 0x050000	
#include <QtWidgets>
#else
#include <QtGui>
#endif

#include "PreviewWindow.h"

PreviewWindow::PreviewWindow(std::string fileName, std::vector<double> radius, vtkSmartPointer<vtkPolyData> triangulateMesh, QWidget *parent)
    :QWidget(parent)
{
    this->setupUi(this);
	
	this->radius = radius;
	mesh = ReadVTKData(fileName);
	
	SegmentationMesh(mesh);

	SetScalarsData(triangulateMesh, radius);

	//set Opacity at 50% for the segmentation
	vtkRendererCollection* rendercollection = this->qvtkWidget->GetRenderWindow()->GetRenderers();
	vtkRenderer* render = rendercollection->GetFirstRenderer();
	vtkActorCollection* actorcollection = render->GetActors();
	actorcollection->InitTraversal();
	vtkActor* actor = actorcollection->GetNextActor();
	actor->GetProperty()->SetOpacity(0.5);

	this->qvtkWidget->update();
	this->connect(this->segmentationCheckBox, SIGNAL(stateChanged(int)), this, SLOT(showSegmentation(int)));
	this->connect(this->opacitySlider, SIGNAL(valueChanged(int)), this, SLOT(segmentationOpacity(int)));
}

vtkPolyData *PreviewWindow::ReadVTKData(std::string fileName)
{
	// Choose the reader based on extension
	vtkPolyDataReader *reader = vtkPolyDataReader::New();
	reader->SetFileName(fileName.c_str());
	reader->Update();
	return reader->GetOutput();
}

void PreviewWindow::SegmentationMesh(vtkPolyData * mesh)
{
	vtkSmartPointer<vtkPolyDataMapper> mapper =
		vtkSmartPointer<vtkPolyDataMapper>::New();
#if VTK_MAJOR_VERSION <= 5
	mapper->SetInput(mesh);
#else
	mapper->SetInputData(mesh);
#endif

	vtkSmartPointer<vtkActor> actor =
		vtkSmartPointer<vtkActor>::New();
	actor->SetMapper(mapper);

	// VTK Renderer
	vtkSmartPointer<vtkRenderer> renderer =
		vtkSmartPointer<vtkRenderer>::New();
	renderer->AddActor(actor);

	// VTK/Qt wedded
	this->qvtkWidget->GetRenderWindow()->AddRenderer(renderer);
	this->qvtkWidget->update();
	renderer->SetBackground(81/256.0, 87/256.0, 110/256.0);
	renderer->ResetCamera();
}

void PreviewWindow::SetScalarsData(vtkSmartPointer<vtkPolyData> triangulateMesh, std::vector<double> radius)
{
	double maxRadius = 0.0;
	double minRadius = 1000.0;
	double range;

	//get the maximum radius
	for (unsigned int i = 0; i < radius.size(); i++) {	
		if (radius[i] > maxRadius)
			maxRadius = radius[i];
	}

	//get the minimum radius
	for (unsigned int i = 0; i < radius.size(); i++) {
		if (radius[i] < minRadius)
			minRadius = radius[i];
	}

	//get the range
	range = maxRadius - minRadius;

	int numPts = triangulateMesh->GetNumberOfPoints();
	vtkSmartPointer<vtkFloatArray> scalars =
		vtkSmartPointer<vtkFloatArray>::New();
	scalars->SetNumberOfValues(numPts);
	for (int i = 0; i < numPts; ++i)
	{
		scalars->SetValue(i, static_cast<float>(radius[i]/range));
	}
	
	vtkSmartPointer<vtkPolyData> poly =
		vtkSmartPointer<vtkPolyData>::New();
	poly->DeepCopy(triangulateMesh);
	poly->GetPointData()->SetScalars(scalars);

	vtkSmartPointer<vtkPolyDataMapper> mapper =
		vtkSmartPointer<vtkPolyDataMapper>::New();
#if VTK_MAJOR_VERSION <= 5
	mapper->SetInput(poly);
#else
	mapper->SetInputData(poly);
#endif
	mapper->ScalarVisibilityOn();
	mapper->SetScalarModeToUsePointData();
	mapper->SetColorModeToMapScalars();

	vtkSmartPointer<vtkActor> actor =
		vtkSmartPointer<vtkActor>::New();
	actor->SetMapper(mapper);

	vtkSmartPointer<vtkScalarBarActor> scalarBar =
		vtkSmartPointer<vtkScalarBarActor>::New();
	scalarBar->SetLookupTable(mapper->GetLookupTable());
	scalarBar->SetTitle("Title");
	scalarBar->SetNumberOfLabels(2);

	vtkSmartPointer<vtkLookupTable> hueLut =
		vtkSmartPointer<vtkLookupTable>::New();

	int numColors = 100; //number of value in the legend
	hueLut->SetScaleToLinear();
	hueLut->SetRange(minRadius/range, maxRadius/range);

	hueLut->SetNumberOfTableValues(numColors);

	double r, g, b;

	for (int i = 0; i < numColors; i++) {
		double val = minRadius + ((double)i / numColors) * range;
		getColorCorrespondingTovalue(val, r, g, b, minRadius, maxRadius, range);
		hueLut->SetTableValue(i, r, g, b);
	}
	hueLut->Build();

	mapper->SetLookupTable(hueLut);
	scalarBar->SetLookupTable(hueLut);
	scalarBar->SetTitle("Radius");
	scalarBar->GetPositionCoordinate()->SetCoordinateSystemToNormalizedViewport();
	scalarBar->GetPositionCoordinate()->SetValue(0.9, 0.05);
	scalarBar->SetWidth(0.1);
	scalarBar->SetHeight(0.4);
	scalarBar->GetTitleTextProperty()->ItalicOff();
	scalarBar->GetLabelTextProperty()->ItalicOff();

	this->qvtkWidget->GetRenderWindow()->GetRenderers()->GetFirstRenderer()->AddActor(actor);
	this->qvtkWidget->GetRenderWindow()->GetRenderers()->GetFirstRenderer()->AddActor2D(scalarBar);
	this->minRad->setText(QString::number(minRadius));
	this->maxRad->setText(QString::number(maxRadius));
}

void PreviewWindow::getColorCorrespondingTovalue(double val,
	double &r, double &g, double &b, double min, double max, double range)
{
	static const int numColorNodes = 3;
	double color[numColorNodes][3] =
	{
		  0.231373, 0.298039, 0.752941,    // blue
		  0.865003, 0.865003, 0.865003,    // white
		  0.705882, 0.0156863, 0.14902     // red
	};

	for (int i = 0; i < (numColorNodes - 1); i++)
	{
		double currFloor = min + ((double)i / (numColorNodes - 1)) * range;
		double currCeil = min + ((double)(i + 1) / (numColorNodes - 1)) * range;

		if ((val >= currFloor) && (val <= currCeil))
		{
			double currFraction = (val - currFloor) / (currCeil - currFloor);
			r = color[i][0] * (1.0 - currFraction) + color[i + 1][0] * currFraction;
			g = color[i][1] * (1.0 - currFraction) + color[i + 1][1] * currFraction;
			b = color[i][2] * (1.0 - currFraction) + color[i + 1][2] * currFraction;
		}
	}
}

void PreviewWindow::showSegmentation(int state) {
	vtkRendererCollection* rendercollection = this->qvtkWidget->GetRenderWindow()->GetRenderers();
	vtkRenderer* render = rendercollection->GetFirstRenderer();
	vtkActorCollection* actorcollection = render->GetActors();
	actorcollection->InitTraversal();
	vtkActor* actor = actorcollection->GetNextActor();
	if (actor != NULL) {
		if (state == Qt::Unchecked) {
			actor->VisibilityOff();
			this->segmentationCheckBox->setChecked(false);
			this->label->setDisabled(true);
			this->opacitySlider->setDisabled(true);
		}
		else {
			actor->VisibilityOn();
			this->segmentationCheckBox->setChecked(true);
			this->label->setDisabled(false);
			this->opacitySlider->setDisabled(false);
		}
		this->qvtkWidget->GetRenderWindow()->Render();
	}
}

void PreviewWindow::segmentationOpacity(int opacity) {
	vtkRendererCollection* rendercollection = this->qvtkWidget->GetRenderWindow()->GetRenderers();
	vtkRenderer* render = rendercollection->GetFirstRenderer();
	vtkActorCollection* actorcollection = render->GetActors();
	actorcollection->InitTraversal();
	vtkActor* actor = actorcollection->GetNextActor();
	if (actor != NULL) {
		double trans = opacity / 100.0;
		actor->GetProperty()->SetOpacity(trans);
		this->qvtkWidget->update();
	}
	this->qvtkWidget->GetRenderWindow()->Render();
}
