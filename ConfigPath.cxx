#include <QtCore/QtGlobal>

#if QT_VERSION >= 0x050000
    #include <QtWidgets>
#else
    #include <QtGui>
#endif

#include "ConfigPath.h"

configPath::configPath(QWidget *parent)
    :QDialog(parent)
{
	QSettings settings(QApplication::applicationDirPath() + "/settings.ini", QSettings::IniFormat);

    pathVoronoiLabel = new QLabel(tr("QVoronoi Path"));
    pathVoronoiEdit = new QLineEdit;
    pathVoronoiLabel->setBuddy(pathVoronoiEdit);
	pathVoronoiEdit->setText(settings.value("pathVoronoi", "").toString());

	pathVtklevelLabel = new QLabel(tr("vtklevelset Path"));
	pathVtklevelEdit = new QLineEdit;
	pathVtklevelLabel->setBuddy(pathVtklevelEdit);
	pathVtklevelEdit->setText(settings.value("pathVtklevel", "").toString());

	pathC3dLabel = new QLabel(tr("c3d Path"));
	pathC3dEdit = new QLineEdit;
	pathC3dLabel->setBuddy(pathC3dEdit);
	pathC3dEdit->setText(settings.value("pathC3d", "").toString());

    browseVoronoiButton = new QPushButton(tr("Browse.."));
	browseVtklevelButton = new QPushButton(tr("Browse.."));
	browseC3dButton = new QPushButton(tr("Browse.."));

    done = new QPushButton(tr("Done"));
    done->setDefault(true);

    QHBoxLayout *voronoiLayout = new QHBoxLayout;
    voronoiLayout->addWidget(pathVoronoiLabel);
    voronoiLayout->addWidget(pathVoronoiEdit);
    voronoiLayout->addWidget(browseVoronoiButton);

	QHBoxLayout *vtktlevelLayout = new QHBoxLayout;
	vtktlevelLayout->addWidget(pathVtklevelLabel);
	vtktlevelLayout->addWidget(pathVtklevelEdit);
	vtktlevelLayout->addWidget(browseVtklevelButton);

	QHBoxLayout *c3dLayout = new QHBoxLayout;
	c3dLayout->addWidget(pathC3dLabel);
	c3dLayout->addWidget(pathC3dEdit);
	c3dLayout->addWidget(browseC3dButton);

    QVBoxLayout *main = new QVBoxLayout;
    main->addLayout(voronoiLayout);
	main->addLayout(vtktlevelLayout);
	main->addLayout(c3dLayout);
    main->addWidget(done);

    QGridLayout *grid = new QGridLayout;
    grid->addLayout(main, 0, 0);
    setLayout(grid);
    setWindowTitle(tr("Configure the GUI"));

    connect(browseVoronoiButton, SIGNAL(clicked()), this, SLOT(browseVoronoi()));
	connect(browseVtklevelButton, SIGNAL(clicked()), this, SLOT(browseVtklevel()));
	connect(browseC3dButton, SIGNAL(clicked()), this, SLOT(browseC3d()));
	connect(done, SIGNAL(clicked()), this, SLOT(accept()));
}

void configPath::browseVoronoi()
{
    QString directory =
            QDir::toNativeSeparators(QFileDialog::getOpenFileName(this, tr("Qvoronoi path"), QDir::currentPath()));

        if (!directory.isEmpty()) {
            pathVoronoiEdit->setText(directory);
        }
}

void configPath::browseVtklevel()
{
	QString directory =
		QDir::toNativeSeparators(QFileDialog::getOpenFileName(this, tr("Vtklevelset path"), QDir::currentPath()));

	if (!directory.isEmpty()) {
		pathVtklevelEdit->setText(directory);
	}
}

void configPath::browseC3d()
{
	QString directory =
		QDir::toNativeSeparators(QFileDialog::getOpenFileName(this, tr("C3d path"), QDir::currentPath()));

	if (!directory.isEmpty()) {
		pathC3dEdit->setText(directory);
	}
}
