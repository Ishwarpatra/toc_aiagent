@echo off
setlocal enabledelayedexpansion
set SRC=.\toc_aiagent_java\src\main\java
set OUT=.\toc_aiagent_java\out
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"
set FILES=
for /r "%SRC%" %%f in (*.java) do (
  set FILES=!FILES! "%%~ff"
)

echo Compiling all Java sources
javac -d "%OUT%" !FILES!
if errorlevel 1 (
  echo Compilation failed
  exit /b 1
)

echo Running application
java -cp "%OUT%" tocaiagent.App
