@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d "C:\Users\crade\Desktop\investor intelligence\Investor-Intelligence-Pipeline\clone\Investor-Intelligence-Pipeline-main\pgvector-install"
set "PGROOT=C:\Program Files\PostgreSQL\18"
nmake /F Makefile.win install
