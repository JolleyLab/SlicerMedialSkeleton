#ifndef ADDLABELDIALOG_H
#define ADDLABELDIALOG_H

#include <QDialog>
#include "global.h"

QT_BEGIN_NAMESPACE
class QDialogButtonBox;
class QGroupBox;
class QLabel;
class QLineEdit;
class QPushButton;
QT_END_NAMESPACE

//! [0]
class AddLabelDialog : public QDialog
{
    Q_OBJECT

public:
    AddLabelDialog(QWidget *parent = 0);

    QLabel *name;
    QLineEdit *nameEdit;
    QPushButton *chooseColor;
    QLabel *colorLabel;
    QLabel *indexLabel;
	QLabel *index;
    QPushButton *done;
    QColor color;

	int labelIndex;

    private slots:
        void accept();
        void setColor();
};
//! [0]
#endif 
