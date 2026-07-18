@ECHO OFF
REM ==========================================================================
REM  Fulfilment service build - run from the VDLEV drive (E:) in the WIN3.0
REM  DOSBox.  Produces TWO Windows 1.01 apps:
REM    VDLOVV.EXE - the monitor (owns COM2; links COMM.C)
REM    VDLEV.EXE  - the dummy service (Windows-messages only; no COMM)
REM  Same hybrid toolchain as VINDAASEN/BUILD.BAT, but no RC step (no
REM  resources), and NEHDR (winver 1.0 + NEIERR guard) per exe.
REM ==========================================================================
SET PATH_=%PATH%
SET INCLUDE_=%INCLUDE%
SET LIB_=%LIB%

REM --- 1) compile ---------------------------------------------------------
SET PATH=C:\QC25\BIN;C:\QCWIN\BIN
SET INCLUDE=C:\QCWIN\INCLUDE
qcl -c -AS -Gw -Zp -W3 VDLOVV.C VDLEV.C COMM.C

REM --- 2) link (two exes) -------------------------------------------------
SET LIB=C:\WINLIB.10
link /NOD /A:16 VDLOVV+COMM+CSUP,,,C51STUBS+LIBH+SLIBW+SWINLIBC+SLIBC,VDLOVV.DEF
link /NOD /A:16 VDLEV+CSUP,,,C51STUBS+LIBH+SLIBW+SWINLIBC+SLIBC,VDLEV.DEF

REM --- 3) winver fixup + NEIERR guard (per exe; delete on failure) --------
SET PATH=C:\SDK101\BIN;C:\QCWIN\BIN;C:\TOOLS
IF NOT EXIST VDLOVV.EXE GOTO LINKFAIL
NEHDR VDLOVV.EXE /WVER:1.0
IF ERRORLEVEL 1 GOTO NEFAILA
IF NOT EXIST VDLEV.EXE GOTO LINKFAIL
NEHDR VDLEV.EXE /WVER:1.0
IF ERRORLEVEL 1 GOTO NEFAILB
ECHO *** BUILD OK: VDLOVV.EXE + VDLEV.EXE ***
GOTO DONE

:LINKFAIL
ECHO *** BUILD FAILED: link produced no EXE ***
GOTO DONE
:NEFAILA
ECHO *** BUILD FAILED: VDLOVV NEIERR ***
IF EXIST VDLOVV.EXE DEL VDLOVV.EXE
GOTO DONE
:NEFAILB
ECHO *** BUILD FAILED: VDLEV NEIERR ***
IF EXIST VDLEV.EXE DEL VDLEV.EXE
GOTO DONE

:DONE
SET PATH=%PATH_%
SET INCLUDE=%INCLUDE_%
SET LIB=%LIB_%
