#include <QtCore/QtGlobal>

#if QT_VERSION >= 0x050000
    #include <QtWidgets>
#else
    #include <QtGui>
#endif

#include "importNiftiiWindow.h"

importNiftiiWindow::importNiftiiWindow(QWidget *parent)
    :QDialog(parent)
{
    inputLabel = new QLabel(tr("Input NifTI file: "));
    inputEdit = new QLineEdit;
    inputLabel->setBuddy(inputEdit);
    inputBrowse = new QPushButton(tr("Browse.."));

    outputLabel = new QLabel(tr("Output vtk file: ")); //change later to vtk
    outputEdit = new QLineEdit;
    outputLabel->setBuddy(outputEdit);
    outputBrowse = new QPushButton(tr("Browse.."));

    smoothCheck = new QCheckBox(tr("Smooth ?"));
    sigmaLabel = new QLabel(tr("Sigma value (in vox): "));
    sigmaEdit = new QLineEdit(tr("2"));
    sigmaLabel->setBuddy(sigmaEdit);

    threshLabel1 = new QLabel(tr("Multi-label segmentation's threshold parameters: "));
    u11Label = new QLabel(tr("Lower Threshold: "));
    u11 = new QLineEdit(tr("1"));
    u11Label->setBuddy(u11);
    u21Label = new QLabel(tr("Upper Threshold: "));
    u21 = new QLineEdit(tr("Inf"));
    u21Label->setBuddy(u21);

    threshLabel2 = new QLabel(tr("Level set value thresholding parameters: "));
    u12Label = new QLabel(tr("Lower Threshold: "));
    u12 = new QLineEdit(tr("0.5"));
    u12Label->setBuddy(u12);
    u22Label = new QLabel(tr("Upper Threshold: "));
    u22 = new QLineEdit(tr("Inf"));
    u22Label->setBuddy(u22);

	showAdvancedParams = new QPushButton(tr("Show advanced parameters"));
	hideAdvancedParams = new QPushButton(tr("Hide advanced parameters"));

    done = new QPushButton(tr("Done"));
    done->setDefault(true);
	
	sigmaLabel->setDisabled(true);
	sigmaEdit->setDisabled(true);

	showAdvancedParams->setDisabled(true);

	threshLabel1->hide();
	u11Label->hide();
	u11->hide();
	u21Label->hide();
	u21->hide();

	threshLabel2->hide();
	u12Label->hide();
	u12->hide();
	u22Label->hide();
	u22->hide();

	hideAdvancedParams->hide();

	QGridLayout *main = new QGridLayout;
	main->addWidget(inputLabel, 0, 0);
	main->addWidget(inputEdit, 0, 1);
	main->addWidget(inputBrowse, 0, 2);

	main->addWidget(outputLabel, 1, 0);
	main->addWidget(outputEdit, 1, 1);
	main->addWidget(outputBrowse, 1, 2);

	main->addWidget(smoothCheck, 2, 0);
	main->addWidget(sigmaLabel, 2, 1);
	main->addWidget(sigmaEdit, 2, 2);

	main->addWidget(showAdvancedParams, 3, 1);

	main->addWidget(threshLabel1, 4, 0);
	main->addWidget(u11Label, 4, 1);
	main->addWidget(u11, 4, 2);
	main->addWidget(u21Label, 5, 1);
	main->addWidget(u21, 5, 2);

	main->addWidget(threshLabel2, 6, 0);
	main->addWidget(u12Label, 6, 1);
	main->addWidget(u12, 6, 2);
	main->addWidget(u22Label, 7, 1);
	main->addWidget(u22, 7, 2);
	
	main->addWidget(hideAdvancedParams, 8, 1);
	main->addWidget(done, 9, 2);

	setLayout(main);
	setWindowTitle(tr("Import NifTI file")); 

	connect(done, SIGNAL(clicked()), this, SLOT(accept()));
	connect(smoothCheck, SIGNAL(stateChanged(int)), this, SLOT(checked()));
	connect(inputBrowse, SIGNAL(clicked()), this, SLOT(browseInput()));
	connect(outputBrowse, SIGNAL(clicked()), this, SLOT(browseOutput()));
	connect(showAdvancedParams, SIGNAL(clicked()), this, SLOT(showParams()));
	connect(hideAdvancedParams, SIGNAL(clicked()), this, SLOT(hideParams()));
}

void importNiftiiWindow::accept() {
	if (inputEdit->text().isEmpty())
	{
		QMessageBox::information(this, tr("No input file"), "You need to choose an input file");
		return;
	}
	if (outputEdit->text().isEmpty())
	{
		QMessageBox::information(this, tr("No output file"), "You need to choose an output file");
		return;
	}
	QDialog::accept();
}

void importNiftiiWindow::checked() {
	if (smoothCheck->isChecked()) {
		sigmaLabel->setDisabled(false);
		sigmaEdit->setDisabled(false);

		showAdvancedParams->setDisabled(false);
	}
	else
	{
		sigmaLabel->setDisabled(true);
		sigmaEdit->setDisabled(true);

		showAdvancedParams->setDisabled(true);
		if (showAdvancedParams->isHidden())
			hideParams();
	}

}

void importNiftiiWindow::browseInput()
{
	QString input =	QDir::toNativeSeparators(QFileDialog::getOpenFileName(this, tr("Input niftii file"), QDir::currentPath()));

	if (!input.isEmpty()) {
		inputEdit->setText(input);
	}
}

void importNiftiiWindow::browseOutput()
{
	QString output = QDir::toNativeSeparators(QFileDialog::getOpenFileName(this, tr("Output niftii file"), QDir::currentPath()));

	if (!output.isEmpty()) {
		outputEdit->setText(output);
	}
}

void importNiftiiWindow::showParams() {
	threshLabel1->show();
	u11Label->show();
	u11->show();
	u21Label->show();
	u21->show();

	threshLabel2->show();
	u12Label->show();
	u12->show();
	u22Label->show();
	u22->show();

	hideAdvancedParams->show();
	showAdvancedParams->hide();
}

void importNiftiiWindow::hideParams() {
	threshLabel1->hide();
	u11Label->hide();
	u11->hide();
	u21Label->hide();
	u21->hide();

	threshLabel2->hide();
	u12Label->hide();
	u12->hide();
	u22Label->hide();
	u22->hide();

	hideAdvancedParams->hide();
	showAdvancedParams->show();
}
