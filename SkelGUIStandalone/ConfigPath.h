#ifndef CONFIGPATH_H
#define CONFIGPATH_H

#include <QDialog>

QT_BEGIN_NAMESPACE
class QDialogButtonBox;
class QGroupBox;
class QLabel;
class QLineEdit;
class QPushButton;
QT_END_NAMESPACE

//! [0]
class configPath : public QDialog
{
    Q_OBJECT

public:
    configPath(QWidget *parent = 0);

    QLabel *pathVoronoiLabel;
	QLabel *pathVtklevelLabel;
	QLabel *pathC3dLabel;

    QLineEdit *pathVoronoiEdit;
	QLineEdit *pathVtklevelEdit;
	QLineEdit *pathC3dEdit;

    QPushButton *browseVoronoiButton;
	QPushButton *browseVtklevelButton;
	QPushButton *browseC3dButton;

    QPushButton *done;

    private slots:
        void browseVoronoi();
		void browseVtklevel();
		void browseC3d();
};
//! [0]
#endif // CONFIGPATH_H
