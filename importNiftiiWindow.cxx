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
    inputLabel = new QLabel(tr("Input niftii file: "));
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

    threshLabel1 = new QLabel(tr("Pre-thresholding parameters: "));
    u11Label = new QLabel(tr("Lower Threshold: "));
    u11 = new QLineEdit(tr("1"));
    u11Label->setBuddy(u11);
    u21Label = new QLabel(tr("Upper Threshold: "));
    u21 = new QLineEdit(tr("Inf"));
    u21Label->setBuddy(u21);
    v11Label = new QLabel(tr("Inside Value: "));
    v11 = new QLineEdit(tr("1"));
    v11Label->setBuddy(v11);
    v21Label = new QLabel(tr("Outside Value: "));
    v21 = new QLineEdit(tr("0"));
    v21Label->setBuddy(v21);

    threshLabel2 = new QLabel(tr("Post-thresholding parameters: "));
    u12Label = new QLabel(tr("Lower Threshold: "));
    u12 = new QLineEdit(tr("0.3"));
    u12Label->setBuddy(u12);
    u22Label = new QLabel(tr("Upper Threshold: "));
    u22 = new QLineEdit(tr("Inf"));
    u22Label->setBuddy(u22);
    v12Label = new QLabel(tr("Inside Value: "));
    v12 = new QLineEdit(tr("1"));
    v12Label->setBuddy(v12);
    v22Label = new QLabel(tr("Outside Value: "));
    v22 = new QLineEdit(tr("0"));
    v22Label->setBuddy(v22);

    done = new QPushButton(tr("Done"));
    done->setDefault(true);

	sigmaLabel->setDisabled(true);
	sigmaEdit->setDisabled(true);

	threshLabel1->setDisabled(true);
	u11Label->setDisabled(true);
	u11->setDisabled(true);
	u21Label->setDisabled(true);
	u21->setDisabled(true);
	v11Label->setDisabled(true);
	v11->setDisabled(true);
	v21Label->setDisabled(true);
	v21->setDisabled(true);

	threshLabel2->setDisabled(true);
	u12Label->setDisabled(true);
	u12->setDisabled(true);
	u22Label->setDisabled(true);
	u22->setDisabled(true);
	v12Label->setDisabled(true);
	v12->setDisabled(true);
	v22Label->setDisabled(true);
	v22->setDisabled(true);

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

	main->addWidget(threshLabel1, 3, 0);
	main->addWidget(u11Label, 3, 1);
	main->addWidget(u11, 3, 2);
	main->addWidget(u21Label, 4, 1);
	main->addWidget(u21, 4, 2);
	main->addWidget(v11Label, 5, 1);
	main->addWidget(v11, 5, 2);
	main->addWidget(v21Label, 6, 1);
	main->addWidget(v21, 6, 2);

	main->addWidget(threshLabel2, 7, 0);
	main->addWidget(u12Label, 7, 1);
	main->addWidget(u12, 7, 2);
	main->addWidget(u22Label, 8, 1);
	main->addWidget(u22, 8, 2);
	main->addWidget(v12Label, 9, 1);
	main->addWidget(v12, 9, 2);
	main->addWidget(v22Label, 10, 1);
	main->addWidget(v22, 10, 2);

	main->addWidget(done, 11, 2);

	setLayout(main);
	setWindowTitle(tr("Import niftii file")); 

	connect(done, SIGNAL(clicked()), this, SLOT(accept()));
	connect(smoothCheck, SIGNAL(stateChanged(int)), this, SLOT(checked()));
	connect(inputBrowse, SIGNAL(clicked()), this, SLOT(browseInput()));
	connect(outputBrowse, SIGNAL(clicked()), this, SLOT(browseOutput()));
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

		threshLabel1->setDisabled(false);
		u11Label->setDisabled(false);
		u11->setDisabled(false);
		u21Label->setDisabled(false);
		u21->setDisabled(false);
		v11Label->setDisabled(false);
		v11->setDisabled(false);
		v21Label->setDisabled(false);
		v21->setDisabled(false);

		threshLabel2->setDisabled(false);
		u12Label->setDisabled(false);
		u12->setDisabled(false);
		u22Label->setDisabled(false);
		u22->setDisabled(false);
		v12Label->setDisabled(false);
		v12->setDisabled(false);
		v22Label->setDisabled(false);
		v22->setDisabled(false);
	}
	else
	{
		sigmaLabel->setDisabled(true);
		sigmaEdit->setDisabled(true);

		threshLabel1->setDisabled(true);
		u11Label->setDisabled(true);
		u11->setDisabled(true);
		u21Label->setDisabled(true);
		u21->setDisabled(true);
		v11Label->setDisabled(true);
		v11->setDisabled(true);
		v21Label->setDisabled(true);
		v21->setDisabled(true);

		threshLabel2->setDisabled(true);
		u12Label->setDisabled(true);
		u12->setDisabled(true);
		u22Label->setDisabled(true);
		u22->setDisabled(true);
		v12Label->setDisabled(true);
		v12->setDisabled(true);
		v22Label->setDisabled(true);
		v22->setDisabled(true);
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
