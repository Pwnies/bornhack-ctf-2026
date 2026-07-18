@ECHO OFF
REM ==========================================================================
REM  VDFLG build - run from this directory's drive letter in the WIN3.0 VM.
REM  Mount VDFLG/ as a drive (e.g. F:) in the dosbox config or manually:
REM      mount F: C:\path\to\VDFLG  (substitute actual host path)
REM  Then: F:  BUILD.BAT
REM ==========================================================================
SET PATH=C:\QC25\BIN;C:\QCWIN\BIN
SET INCLUDE=C:\QCWIN\INCLUDE
SET LIB=C:\WINLIB.10
qcl -c -AS -Gw -Zp -W3 VDFLG.C
IF NOT EXIST VDFLG.OBJ GOTO FAIL
link /NOD /A:16 VDFLG+CSUP,,,C51STUBS+LIBH+SLIBW+SWINLIBC+SLIBC,VDFLG.DEF
IF NOT EXIST VDFLG.EXE GOTO FAIL
SET PATH=C:\SDK101\BIN;C:\QCWIN\BIN;C:\TOOLS
NEHDR VDFLG.EXE /WVER:1.0
IF ERRORLEVEL 1 GOTO NEFAIL
ECHO *** BUILD OK: VDFLG.EXE ***
GOTO DONE
:NEFAIL
ECHO *** BUILD FAILED: NEIERR (unresolved extern -- check no C file API used) ***
IF EXIST VDFLG.EXE DEL VDFLG.EXE
GOTO DONE
:FAIL
ECHO *** BUILD FAILED ***
:DONE
