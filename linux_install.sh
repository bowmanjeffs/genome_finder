#### These commands will install paprica and all its dependencies on Linux. ####
#### They assume nothing other than a base Debian-style Linux installation  ####
#### (e.g. one that uses apt-get).  These commands will not work as-is for  ####
#### OSX, although they will serve as a useful guide for installation on    ####
#### OSX.  Refer to the tutorial at:                                        ####
#### http://www.polarmicrobes.org/installing-paprica-on-mac-osx/.  It is    ####
#### recommended that you run "sudo apt-get update" before executing this   ####
#### script.  This script should be executed as root (e.g. with "sudo").    #### 

cd ~

## Install some packages
sudo apt-get install build-essential
sudo apt-get install git
sudo apt-get install zip

## Install python dependencies, including external python tools
pip3 install numpy
pip3 install biopython
pip3 install joblib
pip3 install pandas
pip3 install seqmagick

## Install RAxML
git clone https://github.com/stamatak/standard-RAxML.git
cd standard-RAxML
sudo make -f Makefile.AVX2.PTHREADS.gcc
rm -f *.o

## Install infernal
cd ~
wget http://eddylab.org/infernal/infernal-1.1.2-linux-intel-gcc.tar.gz
tar -xzvf infernal-1.1.2-linux-intel-gcc.tar.gz
mv infernal-1.1.2-linux-intel-gcc infernal

## Install pplacer
wget https://github.com/matsen/pplacer/releases/download/v1.1.alpha19/pplacer-linux-v1.1.alpha19.zip
unzip pplacer-linux-v1.1.alpha19.zip
mv pplacer-Linux-v1.1.alpha19 pplacer

## Install epa-ng
## Double check that you have all dependencies as described here: https://github.com/Pbdas/epa-ng#installation.
## If the compiler yells at you about not having zlib, you will need to have zlib1g-dev installed, not just zlib1g!

git clone https://github.com/Pbdas/epa-ng.git
cd epa-ng;make

## Modify PATH in .bashrc

cd ~

TEMPNAME=`whoami`
echo "## added by paprica installer" >> .bashrc
echo "PATH=/home/${TEMPNAME}/pplacer:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/.local/bin:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/infernal/binaries:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/infernal/easel:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/standard-RAxML:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/paprica:"'$PATH' >> .bashrc
echo "PATH=/home/${TEMPNAME}/epa-ng/bin:"'$PATH' >> .bashrc
echo "export PATH" >> .bashrc
source .bashrc

## Download paprica - redundant cause that's probably how you got this script
git clone https://github.com/bowmanjeffs/paprica.git
cd paprica
chmod a+x *py
chmod a+x *sh


