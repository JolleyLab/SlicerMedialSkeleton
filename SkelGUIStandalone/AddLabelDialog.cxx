#include <QtCore/QtGlobal>

#if QT_VERSION >= 0x050000
    #include <QtWidgets>
#else
    #include <QtGui>
#endif

#include "AddLabelDialog.h"

AddLabelDialog::AddLabelDialog(QWidget *parent)
    :QDialog(parent)
{
	int curIndex = Global::vectorLabelInfo.size();
    name = new QLabel(tr("Label name:"));

    nameEdit = new QLineEdit;
    name->setBuddy(nameEdit);

    chooseColor = new QPushButton(tr("Label color"));

    colorLabel = new QLabel;

    indexLabel = new QLabel(tr("Triangle index "));

	index = new QLabel(QString::number(curIndex+1));

    done = new QPushButton(tr("OK"));
    done->setDefault(true);

    QHBoxLayout *firstLayout = new QHBoxLayout;
    firstLayout->addWidget(name);
    firstLayout->addWidget(nameEdit);

    QHBoxLayout *secondLayout = new QHBoxLayout;
    secondLayout->addWidget(chooseColor);
    secondLayout->addWidget(colorLabel);

    QHBoxLayout *thirdLayout = new QHBoxLayout;
	thirdLayout->addWidget(indexLabel);
    thirdLayout->addWidget(index);

    QVBoxLayout *mainLayout = new QVBoxLayout;
    mainLayout->addLayout(firstLayout);
    mainLayout->addLayout(secondLayout);
    mainLayout->addLayout(thirdLayout);
    mainLayout->addWidget(done);

    QGridLayout *grid = new QGridLayout;
    grid->addLayout(mainLayout, 0, 0);
    setLayout(grid);
    setWindowTitle(tr("Triangle label"));

	labelIndex = 0;

    connect(chooseColor, SIGNAL(clicked()), this, SLOT(setColor()));
    connect(done, SIGNAL(clicked()), this, SLOT(accept()));

}

void AddLabelDialog::accept(){

    if(nameEdit->text().isEmpty()){
        QMessageBox::information(this, tr("Label Name is Empty"), "You need to specify a label name");
        return;
    }
    if(color.red() == 0 && color.green() == 0 && color.blue() == 0){
        QMessageBox::information(this, tr("Color is not chosen"), "Please choose the color of the label");
        return;
    }

    QDialog::accept();
}

void AddLabelDialog::setColor(){
    color = QColorDialog::getColor(Qt::green, this, "Select Color", QColorDialog::DontUseNativeDialog);

    if (color.isValid()) {
        colorLabel->setPalette(QPalette(color));
        colorLabel->setAutoFillBackground(true);
    }
}
